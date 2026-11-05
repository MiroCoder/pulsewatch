import asyncio



from fastapi import FastAPI

from app.services.checker import check_url

running_tasks : dict[int, asyncio.Task] = {}

monitor_locks : dict[int, asyncio.Lock] = {}


async def periodic_check(url: str, interval_seconds: int):
    while True:
        print("Start")
        res = await check_url(url)
        print(res)

        await asyncio.sleep(interval_seconds)
        print(f"{interval_seconds} later")

def start_monitor(monitor_id: int, url: str, interval_seconds: int):

    if monitor_id not in running_tasks:
        task =asyncio.create_task(periodic_check(url, interval_seconds))
        running_tasks[monitor_id] = task
    elif monitor_id in running_tasks and running_tasks[monitor_id].done():
        task = asyncio.create_task(periodic_check(url, interval_seconds))
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
            stop_monitor(monitor_id)

            try:
                await task
            except asyncio.CancelledError:
                print("Monitoring stopped")

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