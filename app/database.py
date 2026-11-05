from sqlalchemy.orm import DeclarativeBase, Session
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, echo = True)

def get_db():
    with Session(engine) as session:
        yield session

class Base(DeclarativeBase):
    pass

async_engine = create_async_engine(DATABASE_URL, echo = True)
async_session = async_sessionmaker(async_engine)
async def get_async_db():
    async with async_session() as session:
        yield session