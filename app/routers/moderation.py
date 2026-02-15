import logging

import asyncpg
from fastapi import APIRouter, HTTPException, Request

from app.clients.postgres import get_pg_connection
from app.models.ads import (
    AdRequest,
    AdResponse,
    AdSimpleRequest,
    AsyncPredictResponse,
    ModerationResultResponse,
)
from app.routers.utils import (
    check_kafka,
    check_model,
    get_prediction,
    prepare_features_from_ad,
    prepare_features_from_row,
)

predict_router = APIRouter(prefix="/predict")
simple_predict_router = APIRouter(prefix="/simple_predict")
async_predict_router = APIRouter(prefix="/async_predict")
moderation_result_router = APIRouter(prefix="/moderation_result")


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@predict_router.post("", response_model=AdResponse)
async def predict(ad: AdRequest, request: Request):
    logger.info(f"Запрос: {ad}")

    model = request.app.state.model
    check_model(model)

    features = prepare_features_from_ad(ad)
    proba = get_prediction(model, features)
    response = AdResponse(is_violation=(proba >= 0.5), probability=proba)

    logger.info(f"Ответ: {response}")
    return response


@simple_predict_router.post("", response_model=AdResponse)
async def simple_predict(ad: AdSimpleRequest, request: Request):
    logger.info(f"Запрос: {ad}")

    model = request.app.state.model
    check_model(model)

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
    except asyncpg.PostgresError as e:
        logger.error(f"Ошибка БД: {e}")
        raise HTTPException(status_code=503, detail="Сервис базы данных временно недоступен")

    features = prepare_features_from_row(row)
    proba = get_prediction(model, features)

    return AdResponse(is_violation=proba >= 0.5, probability=float(proba))


@async_predict_router.post("", response_model=AsyncPredictResponse)
async def async_predict(ad: AdSimpleRequest, request: Request):
    logger.info(f"Запрос: {ad}")

    kafka_producer = request.app.state.kafka_producer
    check_kafka(kafka_producer)

    try:
        async with request.app.state.pg_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT item_id FROM advertisement WHERE item_id = $1",
                ad.item_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail=f"item_id={ad.item_id} не найдено")
            ad_id = row["item_id"]
    except asyncpg.PostgresError as e:
        logger.error(f"Ошибка БД: {e}")
        raise HTTPException(status_code=503, detail="Сервис базы данных временно недоступен")

    try:
        async with request.app.state.pg_pool.acquire() as conn:
            task_row = await conn.fetchrow(
                "INSERT INTO moderation_results (item_id, status) VALUES ($1, 'pending') RETURNING id",
                ad_id,
            )
            task_id = task_row["id"]
    except asyncpg.PostgresError as e:
        logger.error(f"Ошибка создания задачи: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при создании задачи модерации")

    try:
        await kafka_producer.send_moderation_request(ad_id)
    except Exception as e:
        logger.error(f"Ошибка Kafka: {e}")
        async with request.app.state.pg_pool.acquire() as conn:
            await conn.execute(
                "UPDATE moderation_results SET status = 'failed' WHERE id = $1",
                task_id,
            )
        raise HTTPException(status_code=500, detail="Ошибка при отправке задачи в очередь")

    return AsyncPredictResponse(
        task_id=task_id, status="pending", message="Moderation request accepted"
    )


@moderation_result_router.get("/{task_id}", response_model=ModerationResultResponse)
async def get_moderation_result(task_id: int, request: Request):
    logger.info(f"Запрос статуса: task_id={task_id}")

    try:
        async with request.app.state.pg_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id as task_id, status, is_violation, probability
                FROM moderation_results 
                WHERE id = $1
                """,
                task_id,
            )

            if not row:
                raise HTTPException(status_code=404, detail=f"Задача {task_id} не найдена")

            return ModerationResultResponse(
                task_id=row["task_id"],
                status=row["status"],
                is_violation=row["is_violation"],
                probability=row["probability"],
            )

    except asyncpg.PostgresError as e:
        logger.error(f"Ошибка БД: {e}")
        raise HTTPException(status_code=503, detail="Сервис базы данных временно недоступен")
