from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as redis

from app.clients import settings

_pool = redis.ConnectionPool.from_url(
    f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
    decode_responses=True,
    max_connections=1,
)


@asynccontextmanager
async def get_redis_connection() -> AsyncGenerator[redis.Redis, None]:
    connection = redis.Redis(connection_pool=_pool)
    try:
        yield connection
    finally:
        pass
