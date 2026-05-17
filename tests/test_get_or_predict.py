"""Тесты для PredictionRepository.get_or_predict — все ветки cache-first логики"""

import json
from unittest.mock import AsyncMock, Mock

import pytest

from app.repositories.prediction import PredictionRepository


def _make_request(mock_redis=None, mock_pool=None):
    request = Mock()
    request.app = Mock()
    request.app.state = Mock()
    request.app.state.redis_storage = mock_redis or AsyncMock()
    request.app.state.pg_pool = mock_pool or Mock()
    return request


# ── get_or_predict: cache hit ─────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_or_predict_cache_hit():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = json.dumps({"is_violation": True, "probability": 0.9, "id": 5})

    request = _make_request(mock_redis=mock_redis)
    repo = PredictionRepository(request=request)

    predict_func = AsyncMock()
    result = await repo.get_or_predict(123, predict_func)

    assert result["from_cache"] is True
    assert result["is_violation"] is True
    assert result["probability"] == 0.9
    predict_func.assert_not_called()


# ── get_or_predict: cache miss, DB hit ────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_or_predict_cache_miss_db_hit():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None  # cache miss

    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {
        "id": 10,
        "is_violation": False,
        "probability": 0.2,
        "status": "completed",
    }

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_conn
    mock_context.__aexit__.return_value = None

    mock_pool = Mock()
    mock_pool.acquire.return_value = mock_context

    request = _make_request(mock_redis=mock_redis, mock_pool=mock_pool)
    repo = PredictionRepository(request=request)

    predict_func = AsyncMock()
    result = await repo.get_or_predict(123, predict_func)

    assert result["from_cache"] is False
    assert result["from_db"] is True
    assert result["is_violation"] is False
    assert result["result_id"] == 10
    predict_func.assert_not_called()

    # результат должен быть закэширован
    mock_redis.set.assert_called_once()


# ── get_or_predict: cache miss, DB miss, predict_func called ──────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_or_predict_cache_miss_db_miss_predict():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    # DB miss: get_moderation_result_from_db
    mock_conn = AsyncMock()
    mock_conn.fetchrow.side_effect = [
        None,  # get_moderation_result_from_db → miss
        {"id": 42},  # save_moderation_result → returns id
    ]

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_conn
    mock_context.__aexit__.return_value = None

    mock_pool = Mock()
    mock_pool.acquire.return_value = mock_context

    request = _make_request(mock_redis=mock_redis, mock_pool=mock_pool)
    repo = PredictionRepository(request=request)

    async def mock_predict():
        return 0.75

    result = await repo.get_or_predict(123, mock_predict)

    assert result["from_cache"] is False
    assert result["from_db"] is False
    assert result["is_violation"] is True
    assert result["probability"] == 0.75
    assert result["result_id"] == 42


# ── get_or_predict: predict_func not callable → used directly ─────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_or_predict_non_callable_predict_func():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    mock_conn = AsyncMock()
    mock_conn.fetchrow.side_effect = [None, {"id": 1}]

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_conn
    mock_context.__aexit__.return_value = None

    mock_pool = Mock()
    mock_pool.acquire.return_value = mock_context

    request = _make_request(mock_redis=mock_redis, mock_pool=mock_pool)
    repo = PredictionRepository(request=request)

    result = await repo.get_or_predict(123, 0.3)

    assert result["from_cache"] is False
    assert result["from_db"] is False
    assert result["probability"] == 0.3


# ── get_moderation_result_from_db: нет completed-записей ──────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_moderation_result_from_db_no_completed():
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = None

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_conn
    mock_context.__aexit__.return_value = None

    mock_pool = Mock()
    mock_pool.acquire.return_value = mock_context

    request = _make_request(mock_pool=mock_pool)
    repo = PredictionRepository(request=request)

    result = await repo.get_moderation_result_from_db(999)
    assert result is None


# ── save_moderation_result ────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_save_moderation_result():
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {"id": 55}

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_conn
    mock_context.__aexit__.return_value = None

    mock_pool = Mock()
    mock_pool.acquire.return_value = mock_pool

    # need two separate contexts since save calls acquire separately
    mock_pool2 = Mock()
    ctx2 = AsyncMock()
    ctx2.__aenter__.return_value = mock_conn
    ctx2.__aexit__.return_value = None
    mock_pool2.acquire.return_value = ctx2

    request = _make_request(mock_pool=mock_pool2)
    repo = PredictionRepository(request=request)

    result_id = await repo.save_moderation_result(123, True, 0.88)
    assert result_id == 55
