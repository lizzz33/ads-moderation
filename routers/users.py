from typing import Sequence

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from errors import UserNotFoundError
from models.users import UserModel
from services.users import UserService


class CreateUserInDto(BaseModel):
    name: str
    password: str
    email: str


class LoginUserInDto(BaseModel):
    login: str
    password: str


router = APIRouter()
root_router = APIRouter()

user_service = UserService()


@router.get("/", status_code=status.HTTP_200_OK)
async def get_many() -> Sequence[UserModel]:
    return await user_service.get_many()


@router.post("/", status_code=status.HTTP_201_CREATED)
async def register(data: CreateUserInDto) -> UserModel:
    return await user_service.register(dict(data))


@router.get("/{raw_user_id}")
async def get(raw_user_id: int) -> UserModel:
    try:
        return await user_service.get(raw_user_id)
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь {raw_user_id} не найден",
        )


@router.get("/current/")
async def get_current(request: Request) -> UserModel:
    raw_user_id = request.cookies.get("x-user-id")

    try:
        return await user_service.get(int(raw_user_id))
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь {raw_user_id} не найден",
        )


@router.patch("/deactivate/{raw_user_id}")
async def deactivate(raw_user_id: int, request: Request) -> UserModel:
    raw_user_id = request.cookies.get("x-user-id")

    if not raw_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

    return await user_service.deactivate(int(raw_user_id))


@router.delete("/{raw_user_id}")
async def delete(raw_user_id: int, request: Request) -> UserModel:
    current_user_id = request.cookies.get("x-user-id")

    if not current_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

    try:
        return await user_service.delete(int(raw_user_id))
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь {raw_user_id} не найден",
        )


@root_router.post("/login")
async def login(
    dto: LoginUserInDto,
    response: Response,
) -> UserModel:
    try:
        user = await user_service.login(dto.login, dto.password)

        response.set_cookie(
            key="x-user-id",
            value=user.id,
        )

        return user
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Логин или пароль не верны",
        )
