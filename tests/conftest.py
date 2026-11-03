from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

import pytest

from app.database import Base
import app.models

from sqlalchemy.orm import Session
from app.database import get_db
from app.main import app
from fastapi.testclient import TestClient


test_engine = create_engine("sqlite://",
                    connect_args = {"check_same_thread": False},
                    poolclass = StaticPool

                            )




def override_get_db():
    with Session(test_engine) as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

