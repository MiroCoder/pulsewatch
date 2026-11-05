import asyncio
import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.database import Base, get_db, get_async_db
import app.models
from app.main import app



@pytest.fixture(autouse=True)
def setup_database(tmp_path):
    db_path = (tmp_path / "test.db").as_posix()

    test_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    async_engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}"
    )

    AsyncTestingSession = async_sessionmaker(
        async_engine,
        expire_on_commit=False,
    )

    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        with Session(test_engine) as session:
            yield session

    async def override_get_async_db():
        async with AsyncTestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_async_db] = override_get_async_db

    yield

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_async_db, None)

    asyncio.run(async_engine.dispose())
    test_engine.dispose()