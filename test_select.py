from app.database import Base, engine
from app.models import Monitor
from sqlalchemy import select
from sqlalchemy.orm import Session

with Session(engine) as session:
    statement = select(Monitor)
    monitors = session.scalars(statement).all()

    for monitor in monitors:
        print(monitor.id, monitor.name, monitor.url)