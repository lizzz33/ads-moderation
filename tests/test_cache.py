from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from app.models.users import UserModel
from app.repositories.users import UserPostgresStorage, UserRedisStorage, UserRepository
from app.services.auth import hash_password

PASSWORD = "qwerty"
hashed_password = hash_password(PASSWORD)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_repository_get_caches_result(mock_request):
    """Тест: при отсутствии в кэше данные берутся из БД и сохраняются в кэш"""
    mock_postgres = AsyncMock(spec=UserPostgresStorage)
    mock_redis = AsyncMock(spec=UserRedisStorage)

    mock_redis.get.return_value = None
    mock_postgres.select.return_value = {
        "id": 1,
        "name": "Test",
        "password": hashed_password,
        "login": "test@test.com",
        "is_blocked": False,
    }

    repo = UserRepository(request=mock_request)
    repo.postgres = mock_postgres
    repo.redis = mock_redis

    result = await repo.get(1)

    mock_redis.get.assert_called_once_with(1)
    mock_postgres.select.assert_called_once_with(1)
    mock_redis.set.assert_called_once_with(1, mock_postgres.select.return_value)

    assert isinstance(result, UserModel)
    assert result.id == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_repository_get_returns_cached(mock_request):
    """Тест: при наличии в кэше данные возвращаются из кэша"""
    mock_postgres = AsyncMock(spec=UserPostgresStorage)
    mock_redis = AsyncMock(spec=UserRedisStorage)

    cached_data = {
        "id": 1,
        "name": "Test",
        "password": hashed_password,
        "login": "test@test.com",
        "is_blocked": False,
    }
    mock_redis.get.return_value = cached_data

    repo = UserRepository(request=mock_request)
    repo.postgres = mock_postgres
    repo.redis = mock_redis

    result = await repo.get(1)

    mock_redis.get.assert_called_once_with(1)
    mock_postgres.select.assert_not_called()
    mock_redis.set.assert_not_called()

    assert result.id == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_repository_update_deletes_cache(mock_request):
    """Тест: при обновлении пользователя кэш удаляется"""
    mock_postgres = AsyncMock(spec=UserPostgresStorage)
    mock_redis = AsyncMock(spec=UserRedisStorage)
    mock_postgres.update.return_value = {
        "id": 1,
        "name": "Updated",
        "password": hashed_password,
        "login": "test@test.com",
        "is_blocked": False,
    }

    repo = UserRepository(request=mock_request)
    repo.postgres = mock_postgres
    repo.redis = mock_redis

    await repo.update(1, name="Updated")

    mock_redis.delete.assert_called_once_with(1)
    mock_postgres.update.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_postgres_storage_create(mock_request):
    """Тест создания пользователя в PostgreSQL"""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [{"id": 1}, {"id": 2}]

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_conn
    mock_context.__aexit__.return_value = None

    mock_pool = Mock()
    mock_pool.acquire.return_value = mock_context

    mock_conn.fetchrow.return_value = {
        "id": 1,
        "name": "Test",
        "password": hashed_password,
        "email": "test@test.com",
        "is_active": True,
    }
    mock_request.app.state.pg_pool = mock_pool

    storage = UserPostgresStorage(request=mock_request)
    result = await storage.create("Test", hashed_password, "test@test.com")

    assert result["id"] == 1
    mock_conn.fetchrow.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_set_get_simple(mock_request):
    """Тест сохранения данных в Redis через pipeline"""
    mock_redis_client = AsyncMock()
    mock_redis_client.__aenter__ = AsyncMock(return_value=mock_redis_client)
    mock_redis_client.__aexit__ = AsyncMock(return_value=None)

    mock_pipeline = AsyncMock()
    mock_pipeline.set = MagicMock()
    mock_pipeline.expire = MagicMock()
    mock_pipeline.execute = AsyncMock(return_value=None)
    mock_redis_client.pipeline = MagicMock(return_value=mock_pipeline)

    mock_request.app.state.redis_storage = mock_redis_client

    storage = UserRedisStorage(request=mock_request)
    await storage.set(123, {"id": 123, "name": "Test"})

    mock_redis_client.pipeline.assert_called_once()
    mock_pipeline.set.assert_called_once()
    mock_pipeline.expire.assert_called_once()
    mock_pipeline.execute.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_get_found(mock_request):
    """Тест получения существующих данных из Redis"""
    mock_redis_client = AsyncMock()
    mock_redis_client.__aenter__ = AsyncMock(return_value=mock_redis_client)
    mock_redis_client.__aexit__ = AsyncMock(return_value=None)
    mock_redis_client.get = AsyncMock(return_value='{"id": 123, "name": "Test"}')

    mock_request.app.state.redis_storage = mock_redis_client

    storage = UserRedisStorage(request=mock_request)
    result = await storage.get(123)

    mock_redis_client.get.assert_called_once_with("123")
    assert result == {"id": 123, "name": "Test"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_get_not_found(mock_request):
    """Тест получения несуществующих данных из Redis"""
    mock_redis_client = AsyncMock()
    mock_redis_client.__aenter__ = AsyncMock(return_value=mock_redis_client)
    mock_redis_client.__aexit__ = AsyncMock(return_value=None)
    mock_redis_client.get = AsyncMock(return_value=None)

    mock_request.app.state.redis_storage = mock_redis_client

    storage = UserRedisStorage(request=mock_request)
    result = await storage.get(999)

    mock_redis_client.get.assert_called_once_with("999")
    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_delete(mock_request):
    """Тест удаления данных из Redis"""
    mock_redis_client = AsyncMock()
    mock_redis_client.__aenter__ = AsyncMock(return_value=mock_redis_client)
    mock_redis_client.__aexit__ = AsyncMock(return_value=None)
    mock_redis_client.delete = AsyncMock()

    mock_request.app.state.redis_storage = mock_redis_client

    storage = UserRedisStorage(request=mock_request)
    await storage.delete(123)

    mock_redis_client.delete.assert_called_once_with("123")
