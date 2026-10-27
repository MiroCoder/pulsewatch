from app.database import Base, engine
from app.models import Monitor, CheckResult

Base.metadata.create_all(bind=engine)