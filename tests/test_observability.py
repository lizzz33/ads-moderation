"""Тесты observability: ErrorMetricsMiddleware, track_db_query, track_prediction_duration"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import Response

from observability.middleware import ErrorMetricsMiddleware


# ── ErrorMetricsMiddleware ────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_middleware_4xx_increments_counter():
    mock_app = AsyncMock()

    async def mock_call_next(request):
        return Response(status_code=400)

    middleware = ErrorMetricsMiddleware(mock_app)

    scope = {"type": "http", "method": "GET", "path": "/test", "headers": []}
    request = Request(scope)

    with patch("observability.middleware.HTTP_ERRORS_TOTAL") as mock_counter:
        response = await middleware.dispatch(request, mock_call_next)

        assert response.status_code == 400
        mock_counter.labels.assert_called_with(
            status_code="400", method="GET", handler="unknown"
        )
        mock_counter.labels.return_value.inc.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_middleware_5xx_increments_counter():
    async def mock_call_next(request):
        return Response(status_code=500)

    middleware = ErrorMetricsMiddleware(AsyncMock())

    scope = {"type": "http", "method": "POST", "path": "/predict", "headers": []}
    request = Request(scope)

    with patch("observability.middleware.HTTP_ERRORS_TOTAL") as mock_counter:
        response = await middleware.dispatch(request, mock_call_next)

        assert response.status_code == 500
        mock_counter.labels.assert_called_with(
            status_code="500", method="POST", handler="unknown"
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_middleware_200_does_not_increment():
    async def mock_call_next(request):
        return Response(status_code=200)

    middleware = ErrorMetricsMiddleware(AsyncMock())

    scope = {"type": "http", "method": "GET", "path": "/health", "headers": []}
    request = Request(scope)

    with patch("observability.middleware.HTTP_ERRORS_TOTAL") as mock_counter:
        response = await middleware.dispatch(request, mock_call_next)

        assert response.status_code == 200
        mock_counter.labels.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_middleware_unhandled_exception_increments_500():
    async def mock_call_next(request):
        raise RuntimeError("Unhandled")

    middleware = ErrorMetricsMiddleware(AsyncMock())

    scope = {"type": "http", "method": "POST", "path": "/test", "headers": []}
    request = Request(scope)

    with patch("observability.middleware.HTTP_ERRORS_TOTAL") as mock_counter:
        with pytest.raises(RuntimeError):
            await middleware.dispatch(request, mock_call_next)

        mock_counter.labels.assert_called_with(
            status_code="500", method="POST", handler="internal_error"
        )
        mock_counter.labels.return_value.inc.assert_called_once()


# ── track_db_query decorator ──────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_track_db_query_measures_duration():
    from observability.metrics import track_db_query

    with patch("observability.metrics.DB_QUERY_DURATION") as mock_histogram:
        @track_db_query("select")
        async def fake_query():
            return "result"

        result = await fake_query()

        assert result == "result"
        mock_histogram.labels.assert_called_with(query_type="select")
        mock_histogram.labels.return_value.observe.assert_called_once()


# ── track_prediction_duration decorator ───────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_track_prediction_duration_measures():
    from observability.metrics import track_prediction_duration

    with patch("observability.metrics.PREDICTION_DURATION") as mock_histogram:
        @track_prediction_duration
        async def fake_predict():
            return 0.5

        result = await fake_predict()

        assert result == 0.5
        mock_histogram.observe.assert_called_once()
