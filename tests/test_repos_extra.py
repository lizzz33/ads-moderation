"""Дополнительные тесты: UserPostgresStorage.update невалидные колонки, prediction repo get_or_predict, ads repo edge cases"""

from unittest.mock import AsyncMock, Mock

import pytest

from app.errors import UserNotFoundError
from app.repositories.users import UserPostgresStorage, UserRedisStorage
from app.services.auth import hash_password


# ── UserPostgresStorage.update — невалидные колонки ───────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_invalid_columns_raises_value_error(mock_request):
    storage = UserPostgresStorage(request=mock_request)

    with pytest.raises(ValueError, match="Invalid columns"):
        await storage.update(1, role="admin")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_multiple_invalid_columns(mock_request):
    storage = UserPostgresStorage(request=mock_request)

    with pytest.raises(ValueError, match="Invalid columns"):
        await storage.update(1, role="admin", is_superuser=True)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_valid_columns_passes(mock_request):
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {
        "id": 1,
        "name": "Updated",
        "login": "test@test.com",
        "password": "hash",
        "is_blocked": False,
    }

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_conn
    mock_context.__aexit__.return_value = None

    mock_pool = Mock()
    mock_pool.acquire.return_value = mock_context
    mock_request.app.state.pg_pool = mock_pool

    storage = UserPostgresStorage(request=mock_request)
    result = await storage.update(1, name="Updated")

    assert result["name"] == "Updated"
    mock_conn.fetchrow.assert_called_once()


# ── UserPostgresStorage.delete — несуществующий ───────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_nonexistent_raises_user_not_found(mock_request):
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = None  # DELETE ... RETURNING → None

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_conn
    mock_context.__aexit__.return_value = None

    mock_pool = Mock()
    mock_pool.acquire.return_value = mock_context
    mock_request.app.state.pg_pool = mock_pool

    storage = UserPostgresStorage(request=mock_request)

    with pytest.raises(UserNotFoundError):
        await storage.delete(999)


# ── UserPostgresStorage.select — несуществующий ───────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_select_nonexistent_raises_user_not_found(mock_request):
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = None

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_conn
    mock_context.__aexit__.return_value = None

    mock_pool = Mock()
    mock_pool.acquire.return_value = mock_context
    mock_request.app.state.pg_pool = mock_pool

    storage = UserPostgresStorage(request=mock_request)

    with pytest.raises(UserNotFoundError):
        await storage.select(999)


# ── UserPostgresStorage.select_by_login_and_password — неверный пароль


@pytest.mark.unit
@pytest.mark.asyncio
async def test_select_by_login_wrong_password(mock_request):
    hashed = hash_password("correct_password")

    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {
        "id": 1,
        "name": "Test",
        "login": "test@test.com",
        "password": hashed,
        "is_blocked": False,
    }

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_conn
    mock_context.__aexit__.return_value = None

    mock_pool = Mock()
    mock_pool.acquire.return_value = mock_context
    mock_request.app.state.pg_pool = mock_pool

    storage = UserPostgresStorage(request=mock_request)

    with pytest.raises(UserNotFoundError):
        await storage.select_by_login_and_password("test@test.com", "wrong_password")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_select_by_login_correct_password(mock_request):
    hashed = hash_password("my_password")

    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {
        "id": 1,
        "name": "Test",
        "login": "test@test.com",
        "password": hashed,
        "is_blocked": False,
    }

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_conn
    mock_context.__aexit__.return_value = None

    mock_pool = Mock()
    mock_pool.acquire.return_value = mock_context
    mock_request.app.state.pg_pool = mock_pool

    storage = UserPostgresStorage(request=mock_request)
    result = await storage.select_by_login_and_password("test@test.com", "my_password")

    assert result["id"] == 1


# ── UserRedisStorage.set — с параметром ex ────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_set_with_ex(mock_request):
    mock_redis = AsyncMock()
    mock_request.app.state.redis_storage = mock_redis

    storage = UserRedisStorage(request=mock_request)
    await storage.set("user:1", {"id": 1, "name": "Test"}, ex=3600)

    mock_redis.set.assert_called_once()
    call_kwargs = mock_redis.set.call_args
    assert call_kwargs[1].get("ex") == 3600 or (len(call_kwargs[0]) >= 3)


# ── UserRedisStorage — Redis недоступен (ошибка глотается) ────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_get_handles_error(mock_request):
    mock_redis = AsyncMock()
    mock_redis.get.side_effect = Exception("Redis down")
    mock_request.app.state.redis_storage = mock_redis

    storage = UserRedisStorage(request=mock_request)
    result = await storage.get("user:1")

    assert result is None  # ошибка глотается


# ── AdsRepository — закрытое объявление ───────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_ad_for_moderation_closed_ad(mock_request):
    from app.repositories.ads import AdsRepository

    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = None

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_conn
    mock_context.__aexit__.return_value = None

    mock_pool = Mock()
    mock_pool.acquire.return_value = mock_context
    mock_request.app.state.pg_pool = mock_pool

    repo = AdsRepository(request=mock_request)
    result = await repo.get_ad_for_moderation(123)

    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_ad_id_closed_ad_returns_none(mock_request):
    from app.repositories.ads import AdsRepository

    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = None

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_conn
    mock_context.__aexit__.return_value = None

    mock_pool = Mock()
    mock_pool.acquire.return_value = mock_context
    mock_request.app.state.pg_pool = mock_pool

    repo = AdsRepository(request=mock_request)
    result = await repo.get_ad_id(123)

    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_close_ad_nonexistent_returns_false(mock_request):
    from app.repositories.ads import AdsRepository

    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = None

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_conn
    mock_context.__aexit__.return_value = None

    mock_pool = Mock()
    mock_pool.acquire.return_value = mock_context
    mock_request.app.state.pg_pool = mock_pool

    repo = AdsRepository(request=mock_request)
    result = await repo.close_ad(999)

    assert result is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_ad_caches_handles_db_error(mock_request):
    from app.repositories.ads import AdsRepository

    mock_conn = AsyncMock()
    import asyncpg
    mock_conn.fetch.side_effect = asyncpg.PostgresError("DB error")

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_conn
    mock_context.__aexit__.return_value = None

    mock_pool = Mock()
    mock_pool.acquire.return_value = mock_context
    mock_request.app.state.pg_pool = mock_pool

    mock_redis = AsyncMock()
    mock_request.app.state.redis_storage = mock_redis

    repo = AdsRepository(request=mock_request)
    await repo.delete_ad_caches(123)

    # prediction cache should still be deleted even if DB error
    mock_redis.delete.assert_called()
