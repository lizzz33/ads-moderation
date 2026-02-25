import logging
from dataclasses import dataclass
from typing import Any, Mapping, Optional

import asyncpg
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


@dataclass
class ModerationRepository:
    """Репозиторий для работы с результатами модерации"""

    request: Request

    async def create_task(self, item_id: int) -> int:
        """Создание задачи модерации"""
        query = """
            INSERT INTO moderation_results (item_id, status)
            VALUES ($1, 'pending')
            RETURNING id
        """

        try:
            async with self.request.app.state.pg_pool.acquire() as conn:
                row = await conn.fetchrow(query, item_id)
                return row["id"]
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка БД при создании задачи для item_id={item_id}: {e}")
            raise HTTPException(status_code=503, detail="Сервис базы данных временно недоступен")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при создании задачи: {e}")
            raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

    async def mark_task_failed(self, task_id: int, error: str) -> None:
        """Отметить задачу как ошибочную"""
        query = """
            UPDATE moderation_results 
            SET status = 'failed', error_message = $1
            WHERE id = $2
        """

        try:
            async with self.request.app.state.pg_pool.acquire() as conn:
                await conn.execute(query, error, task_id)
                logger.info(f"Задача {task_id} отмечена как failed: {error}")
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка БД при обновлении задачи {task_id}: {e}")
            raise HTTPException(status_code=503, detail="Сервис базы данных временно недоступен")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при обновлении задачи {task_id}: {e}")
            raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

    async def get_task_result(self, task_id: int) -> Optional[Mapping[str, Any]]:
        """Получение результата задачи по ID"""
        query = """
            SELECT 
                id as task_id,
                status,
                is_violation,
                probability
            FROM moderation_results 
            WHERE id = $1
        """

        try:
            async with self.request.app.state.pg_pool.acquire() as conn:
                row = await conn.fetchrow(query, task_id)
                return dict(row) if row else None
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка БД при получении задачи {task_id}: {e}")
            raise HTTPException(status_code=503, detail="Сервис базы данных временно недоступен")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении задачи {task_id}: {e}")
            raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
