from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.clients.postgres import get_pg_connection
from app.errors import UserNotFoundError
from app.models.users import UserModel


@dataclass(frozen=True)
class UserPostgresStorage:
    async def create(self, name: str, password: str, email: str) -> Mapping[str, Any]:
        query = """
            INSERT INTO account (name, password, email)
            VALUES ($1, $2, $3)
            RETURNING *
        """

        async with get_pg_connection() as connection:
            return dict(await connection.fetchrow(query, name, password, email))

    async def delete(self, id: int) -> Mapping[str, Any]:
        query = """
            DELETE FROM account
            WHERE id = $1::INTEGER
            RETURNING *
        """

        async with get_pg_connection() as connection:
            row = await connection.fetchrow(query, id)

            if row:
                return dict(row)

            raise UserNotFoundError()

    async def select(self, id: int) -> Mapping[str, Any]:
        query = """
            SELECT *
            FROM account
            WHERE id = $1::INTEGER
            LIMIT 1
        """

        async with get_pg_connection() as connection:
            row = await connection.fetchrow(query, id)

            if row:
                return dict(row)

            raise UserNotFoundError()

    async def select_by_login_and_password(self, login: str, password: str) -> Mapping[str, Any]:
        query = """
            SELECT *
            FROM account
            WHERE
                email = $1::TEXT
                AND password = $2::TEXT
            LIMIT 1
        """

        async with get_pg_connection() as connection:
            row = await connection.fetchrow(query, login, password)

            if row:
                return dict(row)

            raise UserNotFoundError()

    async def select_many(self) -> Sequence[Mapping[str, Any]]:
        query = """
            SELECT *
            FROM account
        """

        async with get_pg_connection() as connection:
            rows = await connection.fetch(query)

            return [dict(row) for row in rows]

    async def update(self, id: int, **updates: Any) -> Mapping[str, Any]:
        keys, args = [], []

        for key, value in updates.items():
            keys.append(key)
            args.append(value)

        fields_str = ", ".join([f"{key} = ${i + 2}" for i, key in enumerate(keys)])

        query = f"""
            UPDATE account
            SET {fields_str}
            WHERE id = $1::INTEGER
            RETURNING *
        """

        async with get_pg_connection() as connection:
            row = await connection.fetchrow(query, id, *args)

            if row:
                return dict(row)

            raise UserNotFoundError()


@dataclass(frozen=True)
class UserRepository:
    user_postgres_storage: UserPostgresStorage = UserPostgresStorage()

    async def create(self, name: str, password: str, email: str) -> UserModel:
        raw_user = await self.user_postgres_storage.create(name, password, email)
        return UserModel(**raw_user)

    async def get_by_login_and_password(self, login: str, password: str) -> UserModel:
        raw_user = await self.user_postgres_storage.select_by_login_and_password(login, password)
        return UserModel(**raw_user)

    async def get(self, user_id: int) -> UserModel:
        raw_user = await self.user_postgres_storage.select(user_id)
        return UserModel(**raw_user)

    async def delete(self, user_id: int) -> UserModel:
        raw_user = await self.user_postgres_storage.delete(user_id)
        return UserModel(**raw_user)

    async def update(self, user_id: int, **changes: Mapping[str, Any]) -> UserModel:
        raw_user = await self.user_postgres_storage.update(user_id, **changes)
        return UserModel(**raw_user)

    async def get_many(self) -> Sequence[UserModel]:
        return [
            UserModel(**raw_user) for raw_user in await self.user_postgres_storage.select_many()
        ]
