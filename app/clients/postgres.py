import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg


@asynccontextmanager
async def get_pg_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    # TODO: 1. При каждом обращении к БД создается новое соединение
    # TODO: 2. Не учитывается работа в транзакции

    connection: asyncpg.Connection = await asyncpg.connect(
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres"),
        database=os.getenv("DB_NAME", "moderation"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "6432")),
    )

    yield connection

    await connection.close()
