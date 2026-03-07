from typing import Sequence

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.errors import UserNotFoundError
from app.models.users import CreateUserInDto, LoginUserInDto, UserModel
from app.repositories.users import UserRepository
from app.services.users import UserService

root_router = APIRouter()
user_router = APIRouter(prefix="/users")


def get_user_service(request: Request) -> UserService:
    """Создание сервиса с репозиторием для каждого запроса"""
    user_repo = UserRepository(request=request)
    service = UserService()
    service.user_repo = user_repo
    return service


@user_router.get("/", status_code=status.HTTP_200_OK)
async def get_many(request: Request) -> Sequence[UserModel]:
    user_service = get_user_service(request)
    return await user_service.get_many()


@user_router.post("/", status_code=status.HTTP_201_CREATED)
async def register(data: CreateUserInDto, request: Request) -> UserModel:
    user_service = get_user_service(request)
    return await user_service.register(dict(data))


@user_router.get("/current")
async def get_current(request: Request) -> UserModel:
    raw_user_id = request.cookies.get("x-user-id")
    user_service = get_user_service(request)

    try:
        return await user_service.get(int(raw_user_id))
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь {raw_user_id} не найден",
        )


@user_router.get("/{raw_user_id}")
async def get(raw_user_id: int, request: Request) -> UserModel:
    user_service = get_user_service(request)
    try:
        return await user_service.get(raw_user_id)
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь {raw_user_id} не найден",
        )


@user_router.patch("/deactivate/{raw_user_id}")
async def deactivate(raw_user_id: int, request: Request) -> UserModel:
    raw_user_id = request.cookies.get("x-user-id")
    user_service = get_user_service(request)

    if not raw_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

    return await user_service.deactivate(int(raw_user_id))


@user_router.delete("/{raw_user_id}")
async def delete(raw_user_id: int, request: Request) -> UserModel:
    current_user_id = request.cookies.get("x-user-id")
    user_service = get_user_service(request)

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
async def login(dto: LoginUserInDto, request: Request) -> UserModel:
    user_service = get_user_service(request)
    try:
        user = await user_service.login(dto.login, dto.password)
        response = JSONResponse(content=user.model_dump())
        response.set_cookie(key="x-user-id", value=str(user.id))

        return response

    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Логин или пароль не верны",
        )
