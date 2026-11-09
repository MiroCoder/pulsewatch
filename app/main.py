from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel, HttpUrl, Field, ConfigDict

from app.database import engine, get_db, get_async_db, get_repeatable_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Monitor, CheckResult, Incident
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.services.checker import check_url
from contextlib import asynccontextmanager

from app.services.incidents import process_incident
from app.services.scheduler import start_monitor, stop_monitor, running_tasks, restart_monitor

import asyncio
from typing import Literal

from app.services.url_security import TRUSTED_URLS


class MonitorCreate(BaseModel):
    name: str
    url: HttpUrl
    interval_seconds: int = Field(gt=0)

class MonitorReplace(BaseModel):
    name: str
    url: HttpUrl
    interval_Seconds: int = Field(gt=0)
    is_active : bool

class IncidentRead(BaseModel):
    id: int
    monitor_id: int
    started_at: datetime
    resolved_at: datetime | None
    reason: str | None

    model_config = ConfigDict(from_attributes=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    with Session(engine) as session:
        statement = select(Monitor).where(Monitor.is_active.is_(True))
        monitors = session.scalars(statement).all()

        configs = [
            (monitor.id, str(monitor.url), monitor.interval_seconds)
            for monitor in monitors
        ]

    # Database session is closed

    started_ids = []

    for monitor_id, url, interval_seconds in configs:
        if url not in TRUSTED_URLS:
            continue

        start_monitor(monitor_id, url, interval_seconds)
        started_ids.append(monitor_id)

    tasks = [running_tasks[mid] for mid in started_ids]

    try:
        yield
    finally:
        for monitor_id in started_ids:
            stop_monitor(monitor_id)

        await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(lifespan=lifespan)


class MonitorUpdate(BaseModel):
    name: str | None = None
    url: HttpUrl | None = None
    interval_seconds: int | None = Field(default=None, gt=0)
    is_active: bool | None = None


@app.post("/monitors", status_code=201)
async def create_monitor(create: MonitorCreate, session: AsyncSession = Depends(get_async_db)):
    monitor = Monitor(name=create.name,
                      url=str(create.url),
                      interval_seconds=create.interval_seconds
                      )

    url = str(create.url)

    if url not in TRUSTED_URLS:
        raise HTTPException(422, detail= "URL isn't allowed for monitoring")

    session.add(monitor)
    await session.commit()
    await session.refresh(monitor)

    if monitor.is_active:
        start_monitor(monitor.id, str(monitor.url), monitor.interval_seconds)

    return monitor


@app.get("/monitors", status_code=200)
def get_monitors(session: Session = Depends(get_db)):
    statement = select(Monitor)
    monitors = session.scalars(statement).all()
    return monitors


@app.get("/monitors/{monitor_id}", status_code=200)
def get_monitor_by_id(monitor_id: int, session: Session = Depends(get_db)):
    monitor = session.get(Monitor, monitor_id)

    if monitor is None:
        raise HTTPException(status_code=404)

    return monitor


@app.patch("/monitors/{monitor_id}", status_code=200)
async def update_monitor(monitor_id: int, update: MonitorUpdate, session: AsyncSession = Depends(get_async_db)):
    monitor = await session.get(Monitor, monitor_id)

    if monitor is None:
        raise HTTPException(status_code=404)

    update_data = update.model_dump(exclude_unset=True, mode="json")

    for field, value in update_data.items():
        if value is None:
            raise HTTPException(422)


    old_config = (
        str(monitor.url),
        monitor.interval_seconds,
        monitor.is_active
    )
    for field, value in update_data.items():
        setattr(monitor, field, value)

    url = str(monitor.url)
    interval_seconds = monitor.interval_seconds
    is_active = monitor.is_active

    new_config = (
        str(monitor.url),
        monitor.interval_seconds,
        monitor.is_active

    )
    if is_active and url not in TRUSTED_URLS:
        raise HTTPException(422)

    await session.commit()

    task = running_tasks.get(monitor_id)

    task_missing = task is None or task.done()
    needs_restart = is_active and (
            old_config != new_config or task_missing
    )
    if needs_restart:
        await restart_monitor(monitor_id, url, interval_seconds)
    elif is_active == False:
        stop_monitor(monitor_id)
    await session.refresh(monitor)

    return monitor


@app.delete("/monitors/{monitor_id}", status_code=204)
async def delete_monitor(monitor_id: int, session: AsyncSession = Depends(get_async_db)):
    monitor = await session.get(Monitor, monitor_id)

    if monitor is None:
        raise HTTPException(status_code=404)

    await session.delete(monitor)
    await session.commit()
    stop_monitor(monitor_id)


@app.post("/monitors/{monitor_id}/check")
async def check_monitor(monitor_id: int, session: AsyncSession = Depends(get_async_db)):
    async with session.begin():
        monitor = await session.get(Monitor, monitor_id)

        if monitor is None:
            raise HTTPException(status_code=404)

        if not monitor.is_active:
            raise HTTPException(409, detail="Monitor is paused")

        url = str(monitor.url)

    res = await check_url(url)

    try:
        async with session.begin():
                lock_stmt = (
                    select(Monitor.id).where(Monitor.id == monitor_id).with_for_update())

                result = await session.execute(lock_stmt)
                locked_id = result.scalar_one_or_none()

                if locked_id is None:
                    raise HTTPException(404, detail="Monitor deleted")

                check_result = CheckResult(monitor_id=monitor_id,
                                           status_code=res["status_code"],
                                           latency_ms=res["latency_ms"],
                                           error=res["error"]
                                           )
                session.add(check_result)
                await session.flush()

                await process_incident(session, monitor_id)

                check_id = check_result.id
    except IntegrityError:
        raise HTTPException(status_code=409,
        detail="Could not save check due to a database conflict"
    )

    return {"monitor_id": monitor_id,
            "check_id": check_id,
            "status_code": res["status_code"],
            "latency_ms": res["latency_ms"],
            "error": res["error"]
            }


@app.get("/monitors/{monitor_id}/history")
def get_monitoring_history(monitor_id: int,
                           status_code: int | None = None,
                            limit: int = Query(default=10, ge=1, le=100),
                            offset: int = Query(default=0, ge=0),
                           session: Session = Depends(get_db)):

    monitor = session.get(Monitor, monitor_id)
    if monitor is None:
        raise HTTPException(404)

    statement = select(CheckResult).where(
        CheckResult.monitor_id == monitor_id
    )

    if status_code is not None:
        statement = statement.where(CheckResult.status_code == status_code)

    statement = statement.order_by(
            CheckResult.checked_at.desc(),
            CheckResult.id.desc()).limit(limit).offset(offset)

    history = session.scalars(statement).all()

    return history


@app.get("/monitors/{monitor_id}/stats")
def get_monitor_stats(monitor_id: int, session: Session = Depends(get_db)):
    statement = select(Monitor).where(Monitor.id == monitor_id)
    monitor = session.scalar(statement)

    if monitor is None:
        raise HTTPException(404)

    statement3 = select(func.count()).select_from(CheckResult).where(CheckResult.monitor_id == monitor_id)
    total_checks = session.scalar(statement3)

    statement4 = select(func.avg(CheckResult.latency_ms)).where(CheckResult.monitor_id == monitor_id)
    average_latency_ms = session.scalar(statement4)

    statement5 = select(func.count()).select_from(CheckResult).where(
        CheckResult.monitor_id == monitor_id,
        CheckResult.status_code >= 200,
        CheckResult.status_code < 300,
    )
    success = session.scalar(statement5)
    failed = total_checks - success

    if average_latency_ms is not None:
        average_latency_ms = round(average_latency_ms, 2)


    return {
        "monitor_id": monitor_id,
        "total_checks": total_checks,
        "successful_checks": success,
        "failed_checks": failed,
        "average_latency_ms": average_latency_ms
    }

@app.put("/monitors/{monitor_id}")
async def update_full_monitor(monitor_id : int,update : MonitorReplace, session : AsyncSession = Depends(get_async_db)):
    monitor = await session.get(Monitor, monitor_id)
    if monitor is None:
        raise HTTPException(404)

    update_data = update.model_dump(mode="json")
    old_config = (
        str(monitor.url),
        monitor.interval_seconds,
        monitor.is_active
    )
    for field,value in update_data.items():
        setattr(monitor, field, value)

    url = str(monitor.url)
    interval_seconds = monitor.interval_seconds
    is_active = monitor.is_active

    new_config = (
        str(monitor.url),
        monitor.interval_seconds,
        monitor.is_active

    )
    if is_active and url not in TRUSTED_URLS:
        raise HTTPException(422)

    await session.commit()

    task = running_tasks.get(monitor_id)

    task_missing = task is None or task.done()
    needs_restart = is_active and (
            old_config != new_config or task_missing
    )
    if needs_restart:
        await restart_monitor(monitor_id, url, interval_seconds)
    elif is_active == False:
        stop_monitor(monitor_id)

    await session.refresh(monitor)
    return monitor

@app.get("/monitors/{monitor_id}/overview")
async def get_monitor_overview(monitor_id:int, session: AsyncSession = Depends(get_repeatable_db)):
    async with session.begin():
        statement = await session.execute(select(Monitor).where(Monitor.id == monitor_id))
        monitor = statement.scalar_one_or_none()

        if monitor is None:
            raise HTTPException(404, detail = "Monitor not found")

        response = await session.execute(select(func.count(CheckResult.id)).where(CheckResult.monitor_id == monitor_id))
        counts = response.scalar_one()
    return {
        "monitor_id": monitor_id,
        "name": monitor.name,
        "total_checks": counts
    }

@app.get("/monitors/{monitor_id}/incidents", response_model=list[IncidentRead])
async def get_monitor_incidents(
        monitor_id: int,
        status: Literal["all", "open", "resolved"] = "all",
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
        session: AsyncSession = Depends(get_async_db)
):
    statement = select(Monitor).where(Monitor.id == monitor_id)
    monitor = await session.scalar(statement)

    if monitor is None:
        raise HTTPException(404)

    statement2 = select(Incident).where(Incident.monitor_id == monitor_id)

    if status == "open":
            statement2 = statement2.where(Incident.resolved_at.is_(None))
    elif status == "resolved":
        statement2 = statement2.where(Incident.resolved_at.is_not(None))

    statement2 = statement2.order_by(Incident.started_at.desc(), Incident.id.desc()).limit(limit).offset(offset)
    result = await session.execute(statement2)
    incident = result.scalars().all()

    return incident

@app.get("/monitors/{monitor_id}/availability")
async def get_monitor_availability(monitor_id : int,
                                   hours: int = Query(24, ge=1, le=720),
                                   session: AsyncSession = Depends(get_async_db)):
    statement = select(Monitor).where(Monitor.id == monitor_id)
    monitor = await session.scalar(statement)

    if monitor is None:
        raise HTTPException(404)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    statement2 = select(func.count(CheckResult.id), func.count(CheckResult.id).filter(CheckResult.status_code >=200, CheckResult.status_code < 300, CheckResult.error.is_(None))).where(
        CheckResult.monitor_id == monitor_id, CheckResult.checked_at >= cutoff
    )
    result = await session.execute(statement2)
    total, successful = result.one()


    if total == 0:
        success_rate = None
    else:
        success_rate = successful / total * 100

    return {
        "monitor_id": monitor_id,
        "hours": hours,
        "total_checks": total,
        "successful_checks": successful,
        "failed_checks": (total-successful),
        "success_rate": success_rate
    }