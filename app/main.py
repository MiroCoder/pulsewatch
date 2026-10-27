from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, HttpUrl, Field

from app.database import engine, get_db
from app.models import Monitor
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.checker import check_url

class MonitorCreate(BaseModel):
    name: str
    url: HttpUrl
    interval_seconds: int = Field(gt=0)

app = FastAPI()

class MonitorUpdate(BaseModel):
    name: str | None = None
    url: HttpUrl | None = None
    interval_seconds: int | None = Field(default = None, gt=0)



@app.post("/monitors", status_code=201)
def create_monitor(create: MonitorCreate, session: Session = Depends(get_db)):
    monitor = Monitor(name =create.name,
                      url = str(create.url),
                      interval_seconds =create.interval_seconds
                      )


    session.add(monitor)
    session.commit()
    session.refresh(monitor)


    return monitor

@app.get("/monitors", status_code = 200)
def get_monitors(session: Session = Depends(get_db)):
        statement = select(Monitor)
        monitors = session.scalars(statement).all()
        return monitors

@app.get("/monitors/{monitor_id}", status_code = 200)
def get_monitor_by_id(monitor_id : int, session: Session = Depends(get_db)):
        monitor = session.get(Monitor, monitor_id)

        if monitor is None:
            raise HTTPException(status_code=404)

        return monitor

@app.patch("/monitors/{monitor_id}", status_code = 200)
def update_monitor(monitor_id: int, update: MonitorUpdate, session: Session = Depends(get_db)):
        monitor = session.get(Monitor, monitor_id)

        if monitor is None:
            raise HTTPException(status_code = 404)

        update_data = update.model_dump(exclude_unset = True, mode="json")


        for field, value in update_data.items():
            if value is None:
                raise HTTPException(422)

        for field, value in update_data.items():
            setattr(monitor, field, value)

        session.commit()
        session.refresh(monitor)

        return monitor

@app.delete("/monitors/{monitor_id}", status_code = 204)
def delete_monitor(monitor_id: int, session: Session = Depends(get_db)):

        monitor = session.get(Monitor, monitor_id)

        if monitor is None:
            raise HTTPException(status_code=404)

        session.delete(monitor)
        session.commit()

@app.post("/monitors/{monitor_id}/check")
async def check_monitor(monitor_id: int, session: Session = Depends(get_db)):

    monitor = session.get(Monitor,monitor_id)

    if monitor is None:
            raise HTTPException(status_code=404)

    url = str(monitor.url)

    res = await check_url(url)
    return {"monitor_id": monitor_id,
                "status_code": res["status_code"],
                "latency_ms": res["latency_ms"],
                "error": res["error"]
                }