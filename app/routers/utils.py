# utils.py
import logging

import numpy as np
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def check_model(model):
    if model is None:
        logger.error("Модель не загружена")
        raise HTTPException(status_code=503, detail="Модель не загружена")


def check_kafka(producer):
    if producer is None:
        logger.error("Kafka не загружен")
        raise HTTPException(status_code=503, detail="Kafka недоступен")


def prepare_features_from_ad(ad):
    is_verified = 1 if ad.is_verified_seller else 0
    images_norm = min(ad.images_qty / 20.0, 1.0)
    desc_len_norm = min(len(ad.description) / 5000.0, 1.0)
    category_norm = ad.category / 100.0
    return np.array([[is_verified, images_norm, desc_len_norm, category_norm]])


def prepare_features_from_row(row):
    is_verified = 1 if row["is_verified_seller"] else 0
    images_norm = min(row["images_qty"] / 20.0, 1.0) if row["images_qty"] else 0.0
    desc_len_norm = min(len(row["description"] or "") / 5000.0, 1.0)
    category_norm = row["category"] / 100.0
    return np.array([[is_verified, images_norm, desc_len_norm, category_norm]])


def get_prediction(model, features):
    try:
        proba = model.predict(features)[0]
        return proba
    except Exception as e:
        logger.error(f"Ошибка предсказания: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при обработке запроса")
