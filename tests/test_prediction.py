import json
from unittest.mock import AsyncMock, Mock

import pytest

from app.repositories.prediction import PredictionRepository


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_cached_prediction_hit():
    """Тест получения предсказания из кэша (Redis возвращает строку)"""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = json.dumps({"is_violation": True, "probability": 0.9})

    mock_request = Mock()
    mock_request.app.state.redis_storage = mock_redis

    repo = PredictionRepository(request=mock_request)
    result = await repo.get_cached_prediction(123)

    assert result == {"is_violation": True, "probability": 0.9}
    mock_redis.get.assert_called_once_with("prediction:123")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_cached_prediction_miss():
    """Тест отсутствия предсказания в кэше"""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    mock_request = Mock()
    mock_request.app.state.redis_storage = mock_redis

    repo = PredictionRepository(request=mock_request)
    result = await repo.get_cached_prediction(123)

    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cache_prediction():
    """Тест сохранения предсказания в кэш"""
    mock_redis = AsyncMock()

    mock_request = Mock()
    mock_request.app.state.redis_storage = mock_redis

    repo = PredictionRepository(request=mock_request)
    await repo.cache_prediction(123, {"is_violation": True, "probability": 0.9})

    expected_json = json.dumps({"is_violation": True, "probability": 0.9})
    mock_redis.set.assert_called_once_with("prediction:123", expected_json, ex=3600)
