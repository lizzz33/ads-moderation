import logging

import asyncpg
import numpy as np
from fastapi import APIRouter, HTTPException, Request, status

from clients.postgres import get_pg_connection
from models.ads import AdRequest, AdResponse, AdSimpleRequest

predict_router = APIRouter()
simple_predict_router = APIRouter()


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@predict_router.post("/predict", response_model=AdResponse)
async def predict(ad: AdRequest, request: Request):
    logger.info(f"Запрос: {ad}")
    model = request.app.state.model

    if model is None:
        logger.error("Модель не загружена")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Модель не загружена",
        )

    is_verified = 1 if ad.is_verified_seller else 0
    images_norm = min(ad.images_qty / 20.0, 1.0)
    desc_len_norm = min(len(ad.description) / 5000.0, 1.0)
    category_norm = ad.category / 100.0

    features = np.array([[is_verified, images_norm, desc_len_norm, category_norm]])

    try:
        proba = model.predict(features)[0]
    except Exception as e:
        logger.error(f"Ошибка при предсказании: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера при обработке запроса: {str(e)}",
        )

    response = AdResponse(is_violation=(proba >= 0.5), probability=proba)

    logger.info(f"Ответ: {response}")

    return response


@simple_predict_router.post("/simple_predict", response_model=AdResponse)
async def simple_predict(ad: AdSimpleRequest, request: Request):
    logger.info(f"Запрос: {ad}")
    model = request.app.state.model

    if model is None:
        logger.error("Модель не загружена")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Модель не загружена",
        )
    try:
        async with get_pg_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT is_verified_seller, images_qty, description, category 
                FROM advertisement 
                WHERE item_id = $1
            """,
                ad.item_id,
            )

            if not row:
                raise HTTPException(status_code=404, detail="Объявление не найдено")

    except asyncpg.PostgresConnectionError as e:
        logger.error(f"Ошибка подключения к БД: {e}")
        raise HTTPException(status_code=503, detail="Сервис базы данных временно недоступен")

    except asyncpg.PostgresError as e:
        logger.error(f"Ошибка запроса к БД: {e}")
        raise HTTPException(
            status_code=500, detail=f"Ошибка при получении данных из базы: {str(e)}"
        )

    is_verified = 1 if row["is_verified_seller"] else 0
    images_norm = min(row["images_qty"] / 20.0, 1.0) if row["images_qty"] else 0.0
    desc_len_norm = min(len(row["description"] or "") / 5000.0, 1.0)
    category_norm = row["category"] / 100.0

    features = np.array([[is_verified, images_norm, desc_len_norm, category_norm]])

    try:
        proba = model.predict(features)[0]
    except Exception as e:
        logger.error(f"Ошибка при предсказании: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера при обработке запроса: {str(e)}",
        )

    return AdResponse(is_violation=proba >= 0.5, probability=float(proba))
