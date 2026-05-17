from typing import Sequence

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.dependencies import get_current_user
from app.errors import UserNotFoundError
from app.models.token import Token, TokenData
from app.models.users import CreateUserInDto, LoginUserInDto, UserResponse
from app.repositories.users import UserRepository
from app.services.auth import auth_service
from app.services.users import UserService

root_router = APIRouter()
user_router = APIRouter(prefix="/users")


def get_user_service(request: Request) -> UserService:
    """Создание сервиса с репозиторием для каждого запроса"""
    user_repo = UserRepository(request=request)
    return UserService(user_repo=user_repo)


@user_router.post("/", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def register(data: CreateUserInDto, request: Request):
    """Регистрация нового пользователя (доступно всем)"""
    user_service = get_user_service(request)
    user = await user_service.register(dict(data))
    return UserResponse.model_validate(user.model_dump())


@root_router.post("/login", response_model=Token)
async def login(dto: LoginUserInDto, request: Request):
    """Авторизация пользователя, возвращает JWT токен"""
    user_service = get_user_service(request)

    try:
        user = await user_service.get_by_login_and_password(dto.login, dto.password)

        access_token = auth_service.create_access_token(
            data={"sub": str(user.id), "login": user.login}
        )

        return Token(access_token=access_token, token_type="bearer")

    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid login or password",
        )


@user_router.get("/", status_code=status.HTTP_200_OK, response_model=Sequence[UserResponse])
async def get_many(
    request: Request,
    current_user: TokenData = Depends(get_current_user),
):
    user_service = get_user_service(request)
    users = await user_service.get_many()
    return [UserResponse.model_validate(u.model_dump()) for u in users]


@user_router.get("/current", response_model=UserResponse)
async def get_current(
    request: Request,
    current_user: TokenData = Depends(get_current_user),
):
    user_service = get_user_service(request)

    try:
        user = await user_service.get(current_user.user_id)
        return UserResponse.model_validate(user.model_dump())
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь {current_user.user_id} не найден",
        )


@user_router.get("/{user_id}", response_model=UserResponse)
async def get(
    user_id: int,
    request: Request,
    current_user: TokenData = Depends(get_current_user),
):
    user_service = get_user_service(request)
    try:
        user = await user_service.get(user_id)
        return UserResponse.model_validate(user.model_dump())
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь {user_id} не найден",
        )


@user_router.patch("/deactivate/{user_id}", response_model=UserResponse)
async def deactivate(
    user_id: int,
    request: Request,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only deactivate your own account",
        )

    user_service = get_user_service(request)
    user = await user_service.deactivate(user_id)
    return UserResponse.model_validate(user.model_dump())


@user_router.patch("/block/{user_id}", response_model=UserResponse)
async def block_user(
    user_id: int,
    request: Request,
    current_user: TokenData = Depends(get_current_user),
):
    user_service = get_user_service(request)
    user = await user_service.block(user_id)
    return UserResponse.model_validate(user.model_dump())


@user_router.delete("/{user_id}", response_model=UserResponse)
async def delete(
    user_id: int,
    request: Request,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own account",
        )

    user_service = get_user_service(request)
    try:
        user = await user_service.delete(user_id)
        return UserResponse.model_validate(user.model_dump())
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь {user_id} не найден",
        )
