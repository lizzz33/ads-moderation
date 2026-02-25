from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.users import UserModel
from app.repositories.users import UserRedisStorage, UserRepository


@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_repository_get_caches_result():
    """Тест: при отсутствии в кэше данные берутся из БД и сохраняются в кэш"""
    mock_redis = AsyncMock(spec=UserRedisStorage)
    mock_postgres = AsyncMock()

    mock_redis.get.return_value = None
    mock_postgres.select.return_value = {
        "id": 1,
        "name": "Test",
        "password": "hash",
        "email": "test@test.com",
        "is_active": True,
    }

    repo = UserRepository(user_postgres_storage=mock_postgres, user_redis_storage=mock_redis)

    result = await repo.get(1)

    mock_redis.get.assert_called_once_with(1)
    mock_postgres.select.assert_called_once_with(1)
    mock_redis.set.assert_called_once_with(1, mock_postgres.select.return_value)

    assert isinstance(result, UserModel)
    assert result.id == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_repository_get_returns_cached():
    """Тест: при наличии в кэше данные возвращаются из кэша"""
    mock_redis = AsyncMock(spec=UserRedisStorage)
    mock_postgres = AsyncMock()

    cached_data = {
        "id": 1,
        "name": "Test",
        "password": "hash",
        "email": "test@test.com",
        "is_active": True,
    }
    mock_redis.get.return_value = cached_data

    repo = UserRepository(user_postgres_storage=mock_postgres, user_redis_storage=mock_redis)

    result = await repo.get(1)

    mock_redis.get.assert_called_once_with(1)
    mock_postgres.select.assert_not_called()
    mock_redis.set.assert_not_called()

    assert result.id == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_repository_update_deletes_cache():
    """Тест: при обновлении пользователя кэш удаляется"""
    mock_redis = AsyncMock(spec=UserRedisStorage)
    mock_postgres = AsyncMock()
    mock_postgres.update.return_value = {
        "id": 1,
        "name": "Updated",
        "password": "hash",
        "email": "test@test.com",
        "is_active": True,
    }

    repo = UserRepository(user_postgres_storage=mock_postgres, user_redis_storage=mock_redis)

    await repo.update(1, name="Updated")

    mock_redis.delete.assert_called_once_with("1")
    mock_postgres.update.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_set_get_simple():
    """Тест сохранения данных в Redis через pipeline"""
    mock_redis = AsyncMock()
    mock_redis.__aenter__ = AsyncMock(return_value=mock_redis)
    mock_redis.__aexit__ = AsyncMock(return_value=None)

    mock_pipeline = AsyncMock()
    mock_pipeline.set = MagicMock()
    mock_pipeline.expire = MagicMock()
    mock_pipeline.execute = AsyncMock(return_value=None)
    mock_redis.pipeline = MagicMock(return_value=mock_pipeline)

    with patch("app.repositories.users.get_redis_connection", return_value=mock_redis):
        storage = UserRedisStorage()

        await storage.set(123, {"id": 123, "name": "Test"})

        mock_redis.pipeline.assert_called_once()
        mock_pipeline.set.assert_called_once()
        mock_pipeline.expire.assert_called_once()
        mock_pipeline.execute.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_get_found():
    """Тест получения существующих данных из Redis"""
    mock_redis = AsyncMock()
    mock_redis.__aenter__ = AsyncMock(return_value=mock_redis)
    mock_redis.__aexit__ = AsyncMock(return_value=None)
    mock_redis.get = AsyncMock(return_value='{"id": 123, "name": "Test"}')

    with patch("app.repositories.users.get_redis_connection", return_value=mock_redis):
        storage = UserRedisStorage()
        result = await storage.get(123)

        mock_redis.get.assert_called_once_with("123")
        assert result == {"id": 123, "name": "Test"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_get_not_found():
    """Тест получения несуществующих данных из Redis"""
    mock_redis = AsyncMock()
    mock_redis.__aenter__ = AsyncMock(return_value=mock_redis)
    mock_redis.__aexit__ = AsyncMock(return_value=None)
    mock_redis.get = AsyncMock(return_value=None)

    with patch("app.repositories.users.get_redis_connection", return_value=mock_redis):
        storage = UserRedisStorage()
        result = await storage.get(999)

        mock_redis.get.assert_called_once_with("999")
        assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_delete():
    """Тест удаления данных из Redis"""
    mock_redis = AsyncMock()
    mock_redis.__aenter__ = AsyncMock(return_value=mock_redis)
    mock_redis.__aexit__ = AsyncMock(return_value=None)
    mock_redis.delete = AsyncMock()

    with patch("app.repositories.users.get_redis_connection", return_value=mock_redis):
        storage = UserRedisStorage()
        await storage.delete(123)

        mock_redis.delete.assert_called_once_with("123")
