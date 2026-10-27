from sqlalchemy.orm import DeclarativeBase, Session
import os
from sqlalchemy import create_engine

from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, echo = True)

def get_db():
    with Session(engine) as session:
        yield session

class Base(DeclarativeBase):
    pass