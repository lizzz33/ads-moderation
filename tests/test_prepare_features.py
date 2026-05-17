"""Тесты для prepare_features, get_prediction, get_prediction_for_api, check_model, check_kafka"""

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi import HTTPException

from app.errors import PredictionError
from app.routers.utils import (
    check_kafka,
    check_model,
    get_prediction,
    get_prediction_for_api,
    prepare_features,
)


# ── prepare_features ──────────────────────────────────────────────


@pytest.mark.unit
def test_prepare_features_basic():
    row = {
        "is_verified_seller": True,
        "images_qty": 10,
        "description": "Test description",
        "category": 50,
    }
    result = prepare_features(row)

    assert isinstance(result, np.ndarray)
    assert result.shape == (1, 4)
    assert result[0][0] == 1  # is_verified_seller → 1
    assert result[0][1] == pytest.approx(10 / 20.0)  # images_qty normalized
    assert result[0][2] == pytest.approx(len("Test description") / 5000.0)
    assert result[0][3] == pytest.approx(50 / 100.0)


@pytest.mark.unit
def test_prepare_features_not_verified():
    row = {
        "is_verified_seller": False,
        "images_qty": 5,
        "description": "x",
        "category": 1,
    }
    result = prepare_features(row)
    assert result[0][0] == 0


@pytest.mark.unit
def test_prepare_features_zero_images():
    row = {
        "is_verified_seller": False,
        "images_qty": 0,
        "description": "desc",
        "category": 1,
    }
    result = prepare_features(row)
    assert result[0][1] == 0.0


@pytest.mark.unit
def test_prepare_features_large_images_qty_capped():
    row = {
        "is_verified_seller": True,
        "images_qty": 100,
        "description": "desc",
        "category": 1,
    }
    result = prepare_features(row)
    assert result[0][1] == 1.0  # min(100/20, 1.0)


@pytest.mark.unit
def test_prepare_features_empty_description():
    row = {
        "is_verified_seller": False,
        "images_qty": 0,
        "description": "",
        "category": 1,
    }
    result = prepare_features(row)
    assert result[0][2] == 0.0


@pytest.mark.unit
def test_prepare_features_none_description():
    row = {
        "is_verified_seller": False,
        "images_qty": 0,
        "description": None,
        "category": 1,
    }
    result = prepare_features(row)
    assert result[0][2] == 0.0


@pytest.mark.unit
def test_prepare_features_category_zero():
    row = {
        "is_verified_seller": False,
        "images_qty": 0,
        "description": "",
        "category": 0,
    }
    result = prepare_features(row)
    assert result[0][3] == 0.0


@pytest.mark.unit
def test_prepare_features_category_100():
    row = {
        "is_verified_seller": False,
        "images_qty": 0,
        "description": "",
        "category": 100,
    }
    result = prepare_features(row)
    assert result[0][3] == pytest.approx(1.0)


@pytest.mark.unit
def test_prepare_features_long_description_capped():
    row = {
        "is_verified_seller": False,
        "images_qty": 0,
        "description": "x" * 10000,
        "category": 1,
    }
    result = prepare_features(row)
    assert result[0][2] == 1.0  # min(10000/5000, 1.0)


# ── get_prediction ────────────────────────────────────────────────


@pytest.mark.unit
def test_get_prediction_violation():
    mock_model = MagicMock()
    mock_model.predict.return_value = [0.8]

    result = get_prediction(mock_model, np.array([[0, 0, 0, 0]]))

    assert result == 0.8
    mock_model.predict.assert_called_once()


@pytest.mark.unit
def test_get_prediction_no_violation():
    mock_model = MagicMock()
    mock_model.predict.return_value = [0.2]

    result = get_prediction(mock_model, np.array([[0, 0, 0, 0]]))

    assert result == 0.2


@pytest.mark.unit
def test_get_prediction_model_exception_raises_prediction_error():
    mock_model = MagicMock()
    mock_model.predict.side_effect = RuntimeError("model crashed")

    with pytest.raises(PredictionError, match="model crashed"):
        get_prediction(mock_model, np.array([[0, 0, 0, 0]]))


@pytest.mark.unit
def test_get_prediction_model_exception_increments_error_metric():
    mock_model = MagicMock()
    mock_model.predict.side_effect = RuntimeError("boom")

    with patch("app.routers.utils.PREDICTION_ERRORS_TOTAL") as mock_metric:
        with pytest.raises(PredictionError):
            get_prediction(mock_model, np.array([[0, 0, 0, 0]]))

        mock_metric.labels.assert_called_with(error_type="prediction_error")
        mock_metric.labels.return_value.inc.assert_called_once()


# ── get_prediction_for_api ────────────────────────────────────────


@pytest.mark.unit
def test_get_prediction_for_api_success():
    mock_model = MagicMock()
    mock_model.predict.return_value = [0.6]

    result = get_prediction_for_api(mock_model, np.array([[0, 0, 0, 0]]))
    assert result == 0.6


@pytest.mark.unit
def test_get_prediction_for_api_wraps_prediction_error_as_500():
    mock_model = MagicMock()
    mock_model.predict.side_effect = RuntimeError("fail")

    with pytest.raises(HTTPException) as exc_info:
        get_prediction_for_api(mock_model, np.array([[0, 0, 0, 0]]))

    assert exc_info.value.status_code == 500
    assert "предсказания" in exc_info.value.detail


# ── check_model ───────────────────────────────────────────────────


@pytest.mark.unit
def test_check_model_none_raises_503():
    with patch("app.routers.utils.PREDICTION_ERRORS_TOTAL") as mock_metric:
        with pytest.raises(HTTPException) as exc_info:
            check_model(None)

        assert exc_info.value.status_code == 503
        mock_metric.labels.assert_called_with(error_type="model_unavailable")
        mock_metric.labels.return_value.inc.assert_called_once()


@pytest.mark.unit
def test_check_model_valid():
    check_model(MagicMock())  # не выбрасывает


# ── check_kafka ───────────────────────────────────────────────────


@pytest.mark.unit
def test_check_kafka_none_raises_503():
    with pytest.raises(HTTPException) as exc_info:
        check_kafka(None)
    assert exc_info.value.status_code == 503


@pytest.mark.unit
def test_check_kafka_valid():
    check_kafka(MagicMock())  # не выбрасывает
