import logging
import time

import numpy as np
from fastapi import HTTPException

from app.errors import PredictionError
from observability.metrics import (
    MODEL_PREDICTION_PROBABILITY,
    PREDICTION_DURATION,
    PREDICTION_ERRORS_TOTAL,
    PREDICTIONS_TOTAL,
)

logger = logging.getLogger(__name__)


def check_model(model):
    if model is None:
        PREDICTION_ERRORS_TOTAL.labels(error_type="model_unavailable").inc()
        logger.error("Модель не загружена")
        raise HTTPException(status_code=503, detail="Модель не загружена")


def check_kafka(producer):
    if producer is None:
        logger.error("Kafka не загружен")
        raise HTTPException(status_code=503, detail="Kafka недоступен")


def prepare_features(row):
    is_verified = 1 if row["is_verified_seller"] else 0
    images_norm = min(row["images_qty"] / 20.0, 1.0) if row["images_qty"] else 0.0
    desc_len_norm = min(len(row["description"] or "") / 5000.0, 1.0)
    category_norm = row["category"] / 100.0
    return np.array([[is_verified, images_norm, desc_len_norm, category_norm]])


def get_prediction(model, features):
    try:
        start = time.time()
        proba = model.predict(features)[0]
        duration = time.time() - start

        PREDICTION_DURATION.observe(duration)
        MODEL_PREDICTION_PROBABILITY.observe(proba)

        result = "violation" if proba >= 0.5 else "no_violation"
        PREDICTIONS_TOTAL.labels(result=result).inc()

        return proba

    except Exception as e:
        logger.error(f"Ошибка предсказания: {e}")
        PREDICTION_ERRORS_TOTAL.labels(error_type="prediction_error").inc()
        raise PredictionError(str(e)) from e


def get_prediction_for_api(model, features):
    try:
        return get_prediction(model, features)
    except PredictionError:
        raise HTTPException(status_code=500, detail="Ошибка при получении предсказания")
