import asyncio
import httpx

import time





async def check_url(url: str):
    async with httpx.AsyncClient(timeout=5.0) as client:
        start = time.perf_counter()

        try:

            response = await client.get(url)

            elapsed = time.perf_counter() - start

        except httpx.TimeoutException:
            return {"status_code": None,
                    "latency_ms": None,
                    "error": "Timeout"}

        except httpx.RequestError:
            return {"status_code": None,
                    "latency_ms": None,
                    "error": "Connection error"}


        return {"status_code": response.status_code,
                "latency_ms": round(elapsed * 1000, 2),
                "error": None
                }