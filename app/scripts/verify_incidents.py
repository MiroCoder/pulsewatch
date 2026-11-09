from app.database import async_session
from app.models import CheckResult
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
import selectors

from app.services.incidents import process_incident

MONITOR_ID = 6

async def main():
    for status in(500, 503, 200):
        async with async_session() as session:
            async with session.begin():
                check = CheckResult(monitor_id = MONITOR_ID, status_code=status,
                                    latency_ms=100,error=None)

                session.add(check)
                await session.flush()
                await process_incident(session, MONITOR_ID)

        print(f"Processed HTTP {status}")

if __name__ == "__main__":
    asyncio.run(
        main(),
        loop_factory=lambda: asyncio.SelectorEventLoop(
            selectors.SelectSelector()
        )
    )
