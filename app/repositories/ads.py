import logging
from dataclasses import dataclass
from typing import Any, Mapping, Optional

import asyncpg
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


@dataclass
class AdsRepository:
    """Репозиторий для работы с объявлениями, использующий пул соединений из request.app.state"""

    request: Request

    async def get_ad_for_moderation(self, item_id: int) -> Optional[Mapping[str, Any]]:
        """Получение объявления для модерации"""
        query = """
            SELECT 
                a.item_id,
                a.name,
                a.description,
                a.category,
                a.images_qty,
                a.seller_id,
                s.is_verified as is_verified_seller,
                s.username,
                s.email
            FROM advertisement a
            INNER JOIN sellers s ON a.seller_id = s.seller_id
            WHERE a.item_id = $1 AND a.is_closed = FALSE
        """

        try:
            async with self.request.app.state.pg_pool.acquire() as conn:
                row = await conn.fetchrow(query, item_id)
                if row:
                    return dict(row)
                return None
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка БД в get_ad_for_moderation для item_id={item_id}: {e}")
            raise HTTPException(status_code=503, detail="Сервис базы данных временно недоступен")

    async def get_ad_id(self, item_id: int) -> Optional[int]:
        """Получение ID объявления (проверка существования)"""
        query = "SELECT item_id FROM advertisement WHERE item_id = $1 AND is_closed = FALSE"

        try:
            async with self.request.app.state.pg_pool.acquire() as conn:
                row = await conn.fetchrow(query, item_id)
                return row["item_id"] if row else None
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка БД в get_ad_id для item_id={item_id}: {e}")
            raise HTTPException(status_code=503, detail="Сервис базы данных временно недоступен")

    async def get_ad_by_id(self, item_id: int) -> Optional[Mapping[str, Any]]:
        """Получение объявления по ID (включая закрытые) для проверки статуса"""
        query = """
            SELECT 
                a.item_id,
                a.name,
                a.description,
                a.category,
                a.images_qty,
                s.is_verified as is_verified_seller,
                s.seller_id,
                a.is_closed
            FROM advertisement a
            JOIN sellers s ON a.seller_id = s.seller_id
            WHERE a.item_id = $1
        """

        try:
            async with self.request.app.state.pg_pool.acquire() as conn:
                row = await conn.fetchrow(query, item_id)
                if row:
                    return dict(row)
                return None
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка БД в get_ad_by_id для item_id={item_id}: {e}")
            raise HTTPException(status_code=503, detail="Сервис базы данных временно недоступен")

    async def close_ad(self, item_id: int) -> bool:
        """
        Закрытие объявления:
        - Устанавливает is_closed = True
        """
        query = """
            UPDATE advertisement 
            SET is_closed = TRUE, updated_at = CURRENT_TIMESTAMP
            WHERE item_id = $1 AND is_closed = FALSE
            RETURNING item_id
        """

        try:
            async with self.request.app.state.pg_pool.acquire() as conn:
                result = await conn.fetchval(query, item_id)
                return bool(result)
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка БД в close_ad для item_id={item_id}: {e}")
            raise HTTPException(status_code=503, detail="Сервис базы данных временно недоступен")

    async def delete_ad_caches(self, item_id: int, redis_storage) -> None:
        """
        Удаление всех кэшей, связанных с объявлением
        """
        try:
            cache_keys = [
                f"prediction:{item_id}",
            ]

            query = """
                SELECT id FROM moderation_results 
                WHERE item_id = $1
            """

            try:
                async with self.request.app.state.pg_pool.acquire() as conn:
                    rows = await conn.fetch(query, item_id)
                    for row in rows:
                        cache_keys.append(f"moderation_result:{row['id']}")
            except asyncpg.PostgresError as e:
                logger.error(f"Ошибка БД при получении task_id для item_id={item_id}: {e}")

            for key in cache_keys:
                await redis_storage.delete(key)
                logger.info(f"Удален кэш {key} для объявления {item_id}")

        except Exception as e:
            logger.error(f"Ошибка при удалении кэшей для объявления {item_id}: {e}")
