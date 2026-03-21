import asyncio
import json

import pytest

from app.repositories.prediction import PredictionRepository


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_connection(redis_client):
    """Проверка подключения к Redis"""
    try:
        result = await redis_client.ping()
        assert result is True
    except Exception as e:
        pytest.fail(f"Redis connection failed: {e}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_basic_operations(redis_client):
    """Базовые операции set/get/delete с Redis"""
    key = "test:123"
    value = {"id": 123, "name": "Test"}

    await redis_client.set(key, json.dumps(value))

    result = await redis_client.get(key)
    assert json.loads(result) == value

    await redis_client.delete(key)
    result = await redis_client.get(key)
    assert result is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_ttl(redis_client):
    """Проверка, что TTL срабатывает"""

    key = "test:ttl"
    value = {"data": "expire"}
    ttl = 1

    await redis_client.set(key, json.dumps(value), ex=ttl)

    assert await redis_client.get(key) is not None

    await asyncio.sleep(ttl + 0.5)

    assert await redis_client.get(key) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_prediction_cache_integration(mock_request, redis_client):
    """Интеграционный тест кэширования предсказаний"""
    mock_request.app.state.redis_storage = redis_client

    repo = PredictionRepository(request=mock_request)
    item_id = 123
    prediction_data = {"is_violation": True, "probability": 0.95}

    await repo.cache_prediction(item_id, prediction_data)

    cached = await repo.get_cached_prediction(item_id)
    assert cached == prediction_data

    raw = await redis_client.get(f"prediction:{item_id}")
    assert raw is not None
    assert isinstance(raw, str)
    assert json.loads(raw) == prediction_data
