import logging
from dataclasses import dataclass
from datetime import timedelta
from json import dumps, loads
from typing import Any, Mapping, Optional, Sequence

import asyncpg
from fastapi import HTTPException, Request

from app.errors import UserNotFoundError
from app.models.users import UserModel
from app.services.auth import hash_password
from observability.metrics import track_db_query

logger = logging.getLogger(__name__)


@dataclass
class UserPostgresStorage:
    """Репозиторий для работы с пользователями в PostgreSQL"""

    request: Request

    @track_db_query("insert")
    async def create(self, name: str, login: str, password: str) -> Mapping[str, Any]:
        """Создание нового пользователя"""
        query = """
            INSERT INTO account (name, login, password)
            VALUES ($1, $2, $3)
            RETURNING *
        """
        hashed_password = hash_password(password)

        try:
            async with self.request.app.state.pg_pool.acquire() as conn:
                row = await conn.fetchrow(query, name, login, hashed_password)
                return dict(row)
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка БД при создании пользователя {login}: {e}")
            raise HTTPException(status_code=503, detail="Сервис базы данных временно недоступен")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при создании пользователя: {e}")
            raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

    @track_db_query("delete")
    async def delete(self, id: int) -> Mapping[str, Any]:
        """Удаление пользователя по ID"""
        query = """
            DELETE FROM account
            WHERE id = $1::INTEGER
            RETURNING *
        """

        try:
            async with self.request.app.state.pg_pool.acquire() as conn:
                row = await conn.fetchrow(query, id)
                if row:
                    return dict(row)
                raise UserNotFoundError()
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка БД при удалении пользователя {id}: {e}")
            raise HTTPException(status_code=503, detail="Сервис базы данных временно недоступен")
        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при удалении пользователя: {e}")
            raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

    @track_db_query("select")
    async def select(self, id: int) -> Mapping[str, Any]:
        """Получение пользователя по ID"""
        query = """
            SELECT *
            FROM account
            WHERE id = $1::INTEGER
            LIMIT 1
        """

        try:
            async with self.request.app.state.pg_pool.acquire() as conn:
                row = await conn.fetchrow(query, id)
                if row:
                    return dict(row)
                raise UserNotFoundError()
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка БД при получении пользователя {id}: {e}")
            raise HTTPException(status_code=503, detail="Сервис базы данных временно недоступен")
        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении пользователя: {e}")
            raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

    @track_db_query("select")
    async def select_by_login_and_password(self, login: str, password: str) -> Mapping[str, Any]:
        """Получение пользователя по логину и паролю"""
        query = """
            SELECT *
            FROM account
            WHERE
                login = $1::TEXT
                AND password = $2::TEXT
            LIMIT 1
        """
        hashed_password = hash_password(password)

        try:
            async with self.request.app.state.pg_pool.acquire() as conn:
                row = await conn.fetchrow(query, login, hashed_password)
                if row:
                    return dict(row)
                raise UserNotFoundError()
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка БД при поиске пользователя {login}: {e}")
            raise HTTPException(status_code=503, detail="Сервис базы данных временно недоступен")
        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при поиске пользователя: {e}")
            raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

    @track_db_query("select")
    async def select_many(self) -> Sequence[Mapping[str, Any]]:
        """Получение всех пользователей"""
        query = """
            SELECT *
            FROM account
        """

        try:
            async with self.request.app.state.pg_pool.acquire() as conn:
                rows = await conn.fetch(query)
                return [dict(row) for row in rows]
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка БД при получении списка пользователей: {e}")
            raise HTTPException(status_code=503, detail="Сервис базы данных временно недоступен")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении списка пользователей: {e}")
            raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

    @track_db_query("update")
    async def update(self, id: int, **updates: Any) -> Mapping[str, Any]:
        """Обновление данных пользователя"""
        keys, args = [], []

        for key, value in updates.items():
            keys.append(key)
            args.append(value)

        fields_str = ", ".join([f"{key} = ${i + 2}" for i, key in enumerate(keys)])

        query = f"""
            UPDATE account
            SET {fields_str}, updated_at = CURRENT_TIMESTAMP
            WHERE id = $1::INTEGER
            RETURNING *
        """

        try:
            async with self.request.app.state.pg_pool.acquire() as conn:
                row = await conn.fetchrow(query, id, *args)
                if row:
                    return dict(row)
                raise UserNotFoundError()
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка БД при обновлении пользователя {id}: {e}")
            raise HTTPException(status_code=503, detail="Сервис базы данных временно недоступен")
        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при обновлении пользователя: {e}")
            raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

    @track_db_query("update")
    async def block(self, id: int) -> Mapping[str, Any]:
        """Блокировка пользователя"""
        query = """
            UPDATE account
            SET is_blocked = TRUE, updated_at = CURRENT_TIMESTAMP
            WHERE id = $1::INTEGER AND is_blocked = FALSE
            RETURNING *
        """

        try:
            async with self.request.app.state.pg_pool.acquire() as conn:
                row = await conn.fetchrow(query, id)
                if row:
                    return dict(row)

                user = await self.select(id)
                if user:
                    return user
                raise UserNotFoundError()
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка БД при блокировке пользователя {id}: {e}")
            raise HTTPException(status_code=503, detail="Сервис базы данных временно недоступен")
        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при блокировке пользователя: {e}")
            raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@dataclass
class UserRedisStorage:
    """Репозиторий для работы с пользователями в Redis"""

    request: Optional[Request] = None
    _TTL: timedelta = timedelta(days=1)

    async def _get_redis(self):
        """Получение redis клиента из app.state или из request"""
        if self.request and hasattr(self.request.app.state, "redis_storage"):
            return self.request.app.state.redis_storage

        from app.clients.redis import get_redis_connection

        return await get_redis_connection().__aenter__()

    async def set(self, row_id: int, row: Mapping[str, Any]) -> None:
        """Сохранение пользователя в кэш"""
        redis = await self._get_redis()
        try:
            pipeline = redis.pipeline()
            pipeline.set(
                name=str(row_id),
                value=dumps(row),
            )
            pipeline.expire(str(row_id), self._TTL)
            await pipeline.execute()

        except Exception as e:
            logger.error(f"Ошибка Redis при сохранении пользователя {row_id}: {e}")
        finally:
            if not self.request:
                await redis.close()

    async def get(self, row_id: int) -> Mapping[str, Any] | None:
        """Получение пользователя из кэша"""
        redis = await self._get_redis()
        try:
            row = await redis.get(str(row_id))
            if row:
                return loads(row)
            return None
        except Exception as e:
            logger.error(f"Ошибка Redis при получении пользователя {row_id}: {e}")
            return None
        finally:
            if not self.request:
                await redis.close()

    async def delete(self, row_id: int) -> None:
        """Удаление пользователя из кэша"""
        redis = await self._get_redis()
        try:
            await redis.delete(str(row_id))
        except Exception as e:
            logger.error(f"Ошибка Redis при удалении пользователя {row_id}: {e}")
        finally:
            if not self.request:
                await redis.close()


@dataclass
class UserRepository:
    """Основной репозиторий для работы с пользователями"""

    request: Request

    def __post_init__(self):
        self.postgres = UserPostgresStorage(request=self.request)
        self.redis = UserRedisStorage(request=self.request)

    async def create(self, name: str, login: str, password: str) -> UserModel:
        raw_user = await self.postgres.create(name, login, password)
        return UserModel(**raw_user)

    async def get_by_login_and_password(self, login: str, password: str) -> UserModel:
        raw_user = await self.postgres.select_by_login_and_password(login, password)
        return UserModel(**raw_user)

    async def get(self, user_id: int) -> UserModel:
        if raw_user := await self.redis.get(user_id):
            return UserModel(**raw_user)

        raw_user = await self.postgres.select(user_id)
        await self.redis.set(user_id, raw_user)
        return UserModel(**raw_user)

    async def delete(self, user_id: int) -> UserModel:
        raw_user = await self.postgres.delete(user_id)
        return UserModel(**raw_user)

    async def update(self, user_id: int, **changes: Mapping[str, Any]) -> UserModel:
        raw_user = await self.postgres.update(user_id, **changes)
        await self.redis.delete(user_id)
        return UserModel(**raw_user)

    async def get_many(self) -> Sequence[UserModel]:
        raw_users = await self.postgres.select_many()
        return [UserModel(**raw_user) for raw_user in raw_users]

    async def block(self, user_id: int) -> UserModel:
        raw_user = await self.postgres.block(user_id)
        await self.redis.delete(user_id)
        return UserModel(**raw_user)
