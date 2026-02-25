import logging

from fastapi import APIRouter, HTTPException, Request

from app.models.ads import (
    AdRequest,
    AdResponse,
    AdSimpleRequest,
    AsyncPredictResponse,
    CloseAdRequest,
    CloseAdResponse,
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
close_ad_router = APIRouter(prefix="/close")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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

    redis_storage = request.app.state.redis_storage
    cache_key = f"prediction:{ad.item_id}"
    cached_result = await redis_storage.get(cache_key)
    if cached_result:
        logger.info(f"Ответ из кэша для item_id={ad.item_id}")
        return AdResponse(**cached_result)

    model = request.app.state.model
    check_model(model)

    ads_repo = AdsRepository(request=request)

    try:
        row = await ads_repo.get_ad_for_moderation(ad.item_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

    if not row:
        raise HTTPException(status_code=404, detail="Объявление не найдено")

    features = prepare_features(row)
    proba = get_prediction(model, features)
    response = AdResponse(is_violation=proba >= 0.5, probability=float(proba))

    await redis_storage.set(cache_key, response.model_dump())
    logger.info(f"Результат сохранен в кэш для item_id={ad.item_id}")

    return response


@async_predict_router.post("", response_model=AsyncPredictResponse)
async def async_predict(ad: AdSimpleRequest, request: Request):
    logger.info(f"Запрос async_predict для item_id: {ad.item_id}")

    kafka_producer = request.app.state.kafka_producer
    check_kafka(kafka_producer)

    ads_repo = AdsRepository(request=request)
    moderation_repo = ModerationRepository(request=request)

    try:
        ad_id = await ads_repo.get_ad_id(ad.item_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Ошибка при проверке объявления: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

    if not ad_id:
        raise HTTPException(
            status_code=404, detail=f"Объявление с item_id={ad.item_id} не найдено"
        )

    try:
        task_id = await moderation_repo.create_task(ad_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Ошибка создания задачи: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при создании задачи модерации")

    try:
        await kafka_producer.send_moderation_request(ad_id)
    except Exception as e:
        logger.error(f"Ошибка Kafka: {e}")

        try:
            await moderation_repo.mark_task_failed(task_id, f"Ошибка Kafka: {str(e)}")
        except Exception as mark_error:
            logger.error(f"Не удалось отметить задачу {task_id} как ошибочную: {mark_error}")

        raise HTTPException(status_code=500, detail="Ошибка при отправке задачи в очередь")

    return AsyncPredictResponse(
        task_id=task_id, status="pending", message="Moderation request accepted"
    )


@moderation_result_router.get("/{task_id}", response_model=ModerationResultResponse)
async def get_moderation_result(task_id: int, request: Request):
    logger.info(f"Запрос статуса: task_id={task_id}")

    redis_storage = request.app.state.redis_storage
    cache_key = f"moderation_result:{task_id}"

    try:
        cached_result = await redis_storage.get(cache_key)
        if cached_result:
            logger.info(f"Результат из кэша для task_id={task_id}")
            return ModerationResultResponse(**cached_result)
    except Exception as e:
        logger.error(f"Ошибка при чтении из кэша: {e}")

    moderation_repo = ModerationRepository(request=request)

    try:
        result = await moderation_repo.get_task_result(task_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Ошибка при получении задачи {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

    if not result:
        raise HTTPException(status_code=404, detail=f"Задача {task_id} не найдена")

    response = ModerationResultResponse(
        task_id=task_id,
        status=result["status"],
        is_violation=result["is_violation"],
        probability=result["probability"],
    )

    if result["status"] == "completed":
        try:
            await redis_storage.set(cache_key, response.model_dump())
            logger.info(f"Результат сохранен в кэш для task_id={task_id}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении в кэш: {e}")

    return response


@close_ad_router.post("", response_model=CloseAdResponse)
async def close_ad(request: Request, ad_request: CloseAdRequest):
    logger.info(f"Запрос на закрытие объявления item_id: {ad_request.item_id}")

    redis_storage = request.app.state.redis_storage
    ads_repo = AdsRepository(request=request)

    try:
        ad = await ads_repo.get_ad_by_id(ad_request.item_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при проверке объявления: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

    if not ad:
        raise HTTPException(
            status_code=404, detail=f"Объявление с item_id={ad_request.item_id} не найдено"
        )

    if ad.get("is_closed", False):
        return CloseAdResponse(
            success=True,
            message=f"Объявление {ad_request.item_id} уже было закрыто ранее",
            item_id=ad_request.item_id,
        )

    try:
        closed = await ads_repo.close_ad(ad_request.item_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при закрытии объявления: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

    if not closed:
        raise HTTPException(
            status_code=500, detail=f"Не удалось закрыть объявление {ad_request.item_id}"
        )

    await ads_repo.delete_ad_caches(ad_request.item_id, redis_storage)

    logger.info(f"Объявление {ad_request.item_id} успешно закрыто")
    return CloseAdResponse(
        success=True,
        message=f"Объявление {ad_request.item_id} успешно закрыто, кэши очищены",
        item_id=ad_request.item_id,
    )
