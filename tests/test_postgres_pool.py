"""Тесты postgres pool: init_db_pool, close_db_pool"""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from app.clients.postgres import close_db_pool, init_db_pool


@pytest.mark.unit
@pytest.mark.asyncio
async def test_init_db_pool_creates_pool_once():
    import app.clients.postgres as pg_module

    pg_module._pool = None

    mock_pool = object()

    async def fake_create_pool(**kwargs):
        return mock_pool

    with patch("app.clients.postgres.asyncpg.create_pool", side_effect=fake_create_pool):
        pool1 = await init_db_pool()
        assert pool1 is mock_pool

        pool2 = await init_db_pool()
        assert pool2 is mock_pool
        assert pool2 is pool1

    pg_module._pool = None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_close_db_pool():
    import app.clients.postgres as pg_module

    mock_pool = AsyncMock()
    pg_module._pool = mock_pool

    await close_db_pool()

    mock_pool.close.assert_called_once()
    assert pg_module._pool is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_close_db_pool_when_none():
    import app.clients.postgres as pg_module

    pg_module._pool = None
    await close_db_pool()
    assert pg_module._pool is None
