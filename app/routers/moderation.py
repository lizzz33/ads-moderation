# routers/moderation.py
import logging

from fastapi import APIRouter, HTTPException, Request

from app.models.ads import (
    AdRequest,
    AdResponse,
    AdSimpleRequest,
    AsyncPredictResponse,
    ModerationResultResponse,
)
from app.repositories.ads import AdsRepository
from app.repositories.moderation import ModerationRepository
from app.routers.utils import (
    check_kafka,
    check_model,
    get_prediction,
    prepare_features,
)

predict_router = APIRouter(prefix="/predict")
simple_predict_router = APIRouter(prefix="/simple_predict")
async_predict_router = APIRouter(prefix="/async_predict")
moderation_result_router = APIRouter(prefix="/moderation_result")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ads_repo = AdsRepository()
moderation_repo = ModerationRepository()


@predict_router.post("", response_model=AdResponse)
async def predict(ad: AdRequest, request: Request):
    logger.info(f"Запрос: {ad}")

    model = request.app.state.model
    check_model(model)

    features = prepare_features(ad.model_dump())
    proba = get_prediction(model, features)
    response = AdResponse(is_violation=(proba >= 0.5), probability=proba)

    logger.info(f"Ответ: {response}")
    return response


@simple_predict_router.post("", response_model=AdResponse)
async def simple_predict(ad: AdSimpleRequest, request: Request):
    logger.info(f"Запрос simple_predict для item_id: {ad.item_id}")

    model = request.app.state.model
    check_model(model)

    row = await ads_repo.get_ad_for_moderation(ad.item_id)
    if not row:
        raise HTTPException(status_code=404, detail="Объявление не найдено")

    features = prepare_features(row)
    proba = get_prediction(model, features)

    return AdResponse(is_violation=proba >= 0.5, probability=float(proba))


@async_predict_router.post("", response_model=AsyncPredictResponse)
async def async_predict(ad: AdSimpleRequest, request: Request):
    logger.info(f"Запрос async_predict для item_id: {ad.item_id}")

    kafka_producer = request.app.state.kafka_producer
    check_kafka(kafka_producer)

    ad_id = await ads_repo.get_ad_id(ad.item_id)
    if not ad_id:
        raise HTTPException(
            status_code=404, detail=f"Объявление с item_id={ad.item_id} не найдено"
        )

    try:
        task_id = await moderation_repo.create_task(ad_id)
    except Exception as e:
        logger.error(f"Ошибка создания задачи: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при создании задачи модерации")

    try:
        await kafka_producer.send_moderation_request(ad_id)
    except Exception as e:
        logger.error(f"Ошибка Kafka: {e}")
        await moderation_repo.mark_task_failed(task_id, f"Ошибка Kafka: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при отправке задачи в очередь")

    return AsyncPredictResponse(
        task_id=task_id, status="pending", message="Moderation request accepted"
    )


@moderation_result_router.get("/{task_id}", response_model=ModerationResultResponse)
async def get_moderation_result(task_id: int, request: Request):
    logger.info(f"Запрос статуса: task_id={task_id}")

    result = await moderation_repo.get_task_result(task_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Задача {task_id} не найдена")

    return ModerationResultResponse(
        task_id=result["task_id"],
        status=result["status"],
        is_violation=result["is_violation"],
        probability=result["probability"],
    )
