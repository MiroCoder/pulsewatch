from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel, HttpUrl, Field

from app.database import engine, get_db, get_async_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Monitor, CheckResult
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.services.checker import check_url
from contextlib import asynccontextmanager

from app.services.scheduler import start_monitor, stop_monitor, running_tasks

import asyncio


class MonitorCreate(BaseModel):
    name: str
    url: HttpUrl
    interval_seconds: int = Field(gt=0)

class MonitorReplace(BaseModel):
    name: str
    url: HttpUrl
    interval_Seconds: int = Field(gt=0)
    is_active : bool

TRUSTED_URLS = {
    "https://example.com/",
    "https://github.com/",
    "https://www.python.org/",
}


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
def create_monitor(create: MonitorCreate, session: Session = Depends(get_db)):
    monitor = Monitor(name=create.name,
                      url=str(create.url),
                      interval_seconds=create.interval_seconds
                      )

    session.add(monitor)
    session.commit()
    session.refresh(monitor)

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
def update_monitor(monitor_id: int, update: MonitorUpdate, session: Session = Depends(get_db)):
    monitor = session.get(Monitor, monitor_id)

    if monitor is None:
        raise HTTPException(status_code=404)

    update_data = update.model_dump(exclude_unset=True, mode="json")

    for field, value in update_data.items():
        if value is None:
            raise HTTPException(422)

    for field, value in update_data.items():
        setattr(monitor, field, value)

    session.commit()
    session.refresh(monitor)

    return monitor


@app.delete("/monitors/{monitor_id}", status_code=204)
def delete_monitor(monitor_id: int, session: Session = Depends(get_db)):
    monitor = session.get(Monitor, monitor_id)

    if monitor is None:
        raise HTTPException(status_code=404)

    session.delete(monitor)
    session.commit()


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
                check_result = CheckResult(monitor_id=monitor_id,
                                           status_code=res["status_code"],
                                           latency_ms=res["latency_ms"],
                                           error=res["error"]
                                           )
                session.add(check_result)
                await session.flush()
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
def update_full_monitor(monitor_id : int,update : MonitorReplace, session : Session = Depends(get_db)):
    monitor = session.get(Monitor, monitor_id)
    if monitor is None:
        raise HTTPException(404)

    update_data = update.model_dump(mode="json")
    for field,value in update_data.items():
        setattr(monitor, field, value)

    session.commit()
    session.refresh(monitor)
    return monitor