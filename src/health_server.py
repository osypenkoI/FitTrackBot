import time
import os
import psutil
from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/response-time")
async def response_time():
    start = time.perf_counter()
    elapsed = time.perf_counter() - start
    return elapsed


@app.get("/memory")
async def memory_usage():
    process = psutil.Process(os.getpid())
    memory_mb = process.memory_info().rss / 1024 / 1024
    return round(memory_mb, 2)


@app.get("/cpu")
async def cpu_usage():
    cpu_percent = psutil.cpu_percent(interval=0.1)
    return cpu_percent