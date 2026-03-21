import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import asyncpg
from fastapi import Request

from app.clients.settings import REDIS_TTL_PREDICTION
from observability.metrics import track_db_query

logger = logging.getLogger(__name__)


@dataclass
class PredictionRepository:
    """Репозиторий для работы с предсказаниями (с кэшированием)"""

    request: Request

    async def get_cached_prediction(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Получение предсказания из кэша"""
        redis_storage = self.request.app.state.redis_storage
        cache_key = f"prediction:{item_id}"

        try:
            cached = await redis_storage.get(cache_key)
            if cached:
                logger.info(f"Prediction for {item_id} served from cache")
                if isinstance(cached, str):
                    return json.loads(cached)
                return cached
            return None
        except Exception as e:
            logger.error(f"Redis error in get_cached_prediction for {item_id}: {e}")

        return None

    async def cache_prediction(
        self, item_id: int, data: Dict[str, Any], ttl: int = REDIS_TTL_PREDICTION
    ) -> None:
        """Сохранение предсказания в кэш"""
        redis_storage = self.request.app.state.redis_storage
        cache_key = f"prediction:{item_id}"

        try:
            await redis_storage.set(cache_key, json.dumps(data), ex=ttl)
            logger.info(f"Cached prediction for {item_id}")
        except Exception as e:
            logger.error(f"Redis error in cache_prediction for {item_id}: {e}")

    @track_db_query("select")
    async def get_moderation_result_from_db(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Получение результата модерации из БД"""
        query = """
            SELECT id, is_violation, probability, status, processed_at
            FROM moderation_results
            WHERE item_id = $1 AND status = 'completed'
            ORDER BY created_at DESC
            LIMIT 1
        """

        try:
            async with self.request.app.state.pg_pool.acquire() as conn:
                row = await conn.fetchrow(query, item_id)
                if row:
                    return dict(row)
                return None
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка БД в get_moderation_result_from_db для item_id={item_id}: {e}")
            raise

    @track_db_query("insert")
    async def save_moderation_result(
        self, item_id: int, is_violation: bool, probability: float
    ) -> int:
        """Сохранение результата модерации в БД"""
        query = """
            INSERT INTO moderation_results (item_id, is_violation, probability, status)
            VALUES ($1, $2, $3, 'completed')
            RETURNING id
        """

        try:
            async with self.request.app.state.pg_pool.acquire() as conn:
                row = await conn.fetchrow(query, item_id, is_violation, probability)
                return row["id"]
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка БД в save_moderation_result для item_id={item_id}: {e}")
            raise

    async def get_or_predict(self, item_id: int, predict_func, *args, **kwargs) -> Dict[str, Any]:
        """
        Получение предсказания с кэшированием (cache-first)

        Args:
            item_id: ID объявления
            predict_func: функция для получения предсказания
            *args, **kwargs: аргументы для predict_func
        """
        cached = await self.get_cached_prediction(item_id)
        if cached:
            return {
                "from_cache": True,
                "is_violation": cached.get("is_violation"),
                "probability": cached.get("probability"),
                "result_id": cached.get("id"),
            }

        db_result = await self.get_moderation_result_from_db(item_id)
        if db_result:
            await self.cache_prediction(item_id, db_result)
            return {
                "from_cache": False,
                "from_db": True,
                "is_violation": db_result["is_violation"],
                "probability": db_result["probability"],
                "result_id": db_result["id"],
            }

        proba = await predict_func(*args, **kwargs) if callable(predict_func) else predict_func
        is_violation = proba >= 0.5

        result_id = await self.save_moderation_result(item_id, is_violation, proba)

        result_data = {
            "id": result_id,
            "is_violation": is_violation,
            "probability": proba,
            "status": "completed",
        }
        await self.cache_prediction(item_id, result_data)

        return {
            "from_cache": False,
            "from_db": False,
            "is_violation": is_violation,
            "probability": proba,
            "result_id": result_id,
        }
