import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg

_pool = None


async def init_db_pool():
    """Инициализация пула соединений"""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres"),
            database=os.getenv("DB_NAME", "moderation"),
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "6432")),
            min_size=1,
            max_size=10,
        )
    return _pool


async def close_db_pool():
    """Закрытие пула соединений"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def reset_db_pool():
    """Сброс пула (для тестов)"""
    await close_db_pool()


@asynccontextmanager
async def get_pg_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Получение соединения из пула"""
    pool = await init_db_pool()

    async with pool.acquire() as connection:
        try:
            yield connection
        except asyncpg.exceptions.ConnectionDoesNotExistError:
            async with pool.acquire() as new_connection:
                yield new_connection
