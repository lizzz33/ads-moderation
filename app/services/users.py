from typing import Any, Mapping, Sequence

from app.errors import UserNotFoundError
from app.models.users import UserModel


class UserService:
    def __init__(self, user_repo):
        self.user_repo = user_repo

    async def register(self, values: Mapping[str, Any]) -> UserModel:
        return await self.user_repo.create(**values)

    async def login(self, login: str, password: str) -> UserModel:
        try:
            user = await self.user_repo.get_by_login_and_password(login, password)
            return user
        except UserNotFoundError:
            raise ValueError("Invalid login or password")

    async def get(self, user_id: int) -> UserModel:
        return await self.user_repo.get(user_id)

    async def delete(self, user_id: int) -> UserModel:
        return await self.user_repo.delete(user_id)

    async def deactivate(self, user_id: int) -> UserModel:
        return await self.user_repo.update(user_id, is_active=False)

    async def get_many(self) -> Sequence[UserModel]:
        return await self.user_repo.get_many()

    async def block(self, user_id: int) -> UserModel:
        return await self.user_repo.block(user_id)

    async def get_by_login_and_password(self, login: str, password: str) -> UserModel:
        return await self.user_repo.get_by_login_and_password(login, password)
