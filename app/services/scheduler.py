import asyncio

from fastapi import HTTPException

from app.database import async_session
from sqlalchemy import select

from app.models import CheckResult, Monitor
from app.services.checker import check_url

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import logging
from app.services.incidents import process_incident

logger = logging.getLogger(__name__)

running_tasks : dict[int, asyncio.Task] = {}

monitor_locks : dict[int, asyncio.Lock] = {}


async def periodic_check(monitor_id: int, url: str, interval_seconds: int):
    while True:
        logger.info("Check started: monitor_id=%s", monitor_id)
        res = await check_url(url)
        try:
            async with async_session() as session:
                async with session.begin():
                    statement = select(Monitor.id).where(Monitor.id == monitor_id).with_for_update()
                    result = await session.execute(statement)
                    locked_id = result.scalar_one_or_none()

                    if locked_id is None:
                        logger.warning(
                            "Monitor deleted: monitor_id=%s",
                            monitor_id
                        )
                        break

                    check = CheckResult(monitor_id =monitor_id, status_code=res["status_code"], latency_ms= res["latency_ms"], error = res["error"])
                    session.add(check)
                    await session.flush()
                    await process_incident(session, monitor_id)

            logger.info(
                "Check saved: monitor_id=%s status=%s",
                monitor_id,
                res["status_code"]
            )

        except IntegrityError:
            logger.warning(
                "Database integrity conflict: monitor_id=%s",
                monitor_id
            )
            break
        except SQLAlchemyError:
            logger.exception("Database failure: monitor_id=%s", monitor_id)


        await asyncio.sleep(interval_seconds)


def start_monitor(monitor_id: int, url: str, interval_seconds: int):

    if monitor_id not in running_tasks:
        task =asyncio.create_task(periodic_check(monitor_id,url, interval_seconds))
        running_tasks[monitor_id] = task
    elif monitor_id in running_tasks and running_tasks[monitor_id].done():
        task = asyncio.create_task(periodic_check(monitor_id,url, interval_seconds))
        running_tasks[monitor_id] = task
    else:
        pass

def stop_monitor(monitor_id: int):
    task = running_tasks.get(monitor_id)
    if task is None:
        pass
    elif not task.done():
        task.cancel()
        del running_tasks[monitor_id]
    else:
        del running_tasks[monitor_id]

async def restart_monitor(monitor_id: int, url:str, interval_seconds:int):
    lock = monitor_locks.setdefault(monitor_id, asyncio.Lock())


    async with lock:
        task = running_tasks.get(monitor_id)
        if task is not None:
            if task.done():
                if not task.cancelled():
                    error = task.exception()
                    if error is not None:
                        logger.error(
                            "Monitoring failed: monitor_id=%s error=%s",
                            monitor_id,
                            error
                        )
                stop_monitor(monitor_id)

            else:
                stop_monitor(monitor_id)
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info("Monitoring stopped: monitor_id=%s", monitor_id)

        start_monitor(monitor_id, url, interval_seconds)


async def main():

    start_monitor(1, "https://github.com", 10)

    task = running_tasks[1]

    await asyncio.sleep(2)

    stop_monitor(1)

    try:
        await task
    except asyncio.CancelledError:
        print("Monitoring stopped")

    print(running_tasks)

if __name__ == "__main__":
    asyncio.run(main())