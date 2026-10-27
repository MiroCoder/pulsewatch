from app.database import Base, engine
from app.models import Monitor
from sqlalchemy.orm import Session

monitor = Monitor(
    name = "Google",
    url = "https://google.com",
    interval_seconds = 60
)

with Session(engine) as session:
    session.add(monitor)
    session.commit()
    session.refresh(monitor)
    print(monitor.id)