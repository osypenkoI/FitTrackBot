import asyncio
import aiohttp
import time

URLS = [
    "http://127.0.0.1:8000/health",
    "http://127.0.0.1:8000/response-time",
    "http://127.0.0.1:8000/memory",
    "http://127.0.0.1:8000/cpu",
]

USERS = 10
REQUESTS_PER_USER = 60


async def simulate_user(user_id: int):
    async with aiohttp.ClientSession() as session:
        for i in range(REQUESTS_PER_USER):
            for url in URLS:
                start = time.perf_counter()
                async with session.get(url) as response:
                    await response.text()
                elapsed = time.perf_counter() - start
                print(f"User {user_id}, request {i + 1}: {elapsed:.3f}s")
            await asyncio.sleep(0.3)


async def main():
    tasks = [simulate_user(i + 1) for i in range(USERS)]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())