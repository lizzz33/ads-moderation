from dataclasses import dataclass
from typing import Any, Mapping, Optional

from app.clients.postgres import get_pg_connection


@dataclass(frozen=True)
class ModerationRepository:
    async def create_task(self, item_id: int) -> int:
        query = """
            INSERT INTO moderation_results (item_id, status)
            VALUES ($1, 'pending')
            RETURNING id
        """

        async with get_pg_connection() as conn:
            row = await conn.fetchrow(query, item_id)
            return row["id"]

    async def mark_task_failed(self, task_id: int, error: str) -> None:
        query = """
            UPDATE moderation_results 
            SET status = 'failed', error_message = $1
            WHERE id = $2
        """

        async with get_pg_connection() as conn:
            await conn.execute(query, error, task_id)

    async def get_task_result(self, task_id: int) -> Optional[Mapping[str, Any]]:
        query = """
            SELECT 
                id as task_id,
                status,
                is_violation,
                probability
            FROM moderation_results 
            WHERE id = $1
        """

        async with get_pg_connection() as conn:
            row = await conn.fetchrow(query, task_id)
            return dict(row) if row else None
