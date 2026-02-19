from dataclasses import dataclass
from typing import Any, Mapping, Optional

from app.clients.postgres import get_pg_connection


@dataclass(frozen=True)
class AdsRepository:
    async def get_ad_for_moderation(self, item_id: int) -> Optional[Mapping[str, Any]]:
        query = """
            SELECT 
                a.item_id,
                a.name,
                a.description,
                a.category,
                a.images_qty,
                a.seller_id,
                s.is_verified,
                s.username,
                s.email
            FROM advertisement a
            INNER JOIN sellers s ON a.seller_id = s.seller_id
            WHERE a.item_id = $1
        """

        async with get_pg_connection() as conn:
            row = await conn.fetchrow(query, item_id)
            if row:
                data = dict(row)
                data["is_verified_seller"] = data.pop("is_verified")
                return data
            return None

    async def get_ad_id(self, item_id: int) -> Optional[int]:
        query = "SELECT item_id FROM advertisement WHERE item_id = $1"

        async with get_pg_connection() as conn:
            row = await conn.fetchrow(query, item_id)
            return row["item_id"] if row else None
