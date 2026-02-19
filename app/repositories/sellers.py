from dataclasses import dataclass
from typing import Any, Mapping, Optional

from app.clients.postgres import get_pg_connection


@dataclass(frozen=True)
class SellersRepository:
    async def get_seller(self, seller_id: int) -> Optional[Mapping[str, Any]]:
        query = """
            SELECT 
                seller_id,
                username,
                email,
                is_verified
            FROM sellers
            WHERE seller_id = $1
        """

        async with get_pg_connection() as conn:
            row = await conn.fetchrow(query, seller_id)
            return dict(row) if row else None

    async def create_seller(self, username: str, email: str, password: str) -> int:
        query = """
            INSERT INTO sellers (username, email, password)
            VALUES ($1, $2, $3)
            RETURNING seller_id
        """

        async with get_pg_connection() as conn:
            row = await conn.fetchrow(query, username, email, password)
            return row["seller_id"]
