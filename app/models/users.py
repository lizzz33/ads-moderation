from pydantic import BaseModel


class UserResponse(BaseModel):
    id: int
    name: str
    login: str
    is_blocked: bool = True


class UserModel(BaseModel):
    """Только для внутреннего использования"""
    id: int
    name: str
    login: str
    password: str
    is_blocked: bool = True


class CreateUserInDto(BaseModel):
    name: str
    login: str
    password: str


class LoginUserInDto(BaseModel):
    login: str
    password: str
