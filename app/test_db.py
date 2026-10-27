from database import engine
from sqlalchemy import text

with engine.connect() as connection:
    query = text("SELECT 1")
    result = connection.execute(query).scalar_one()
    print(result)