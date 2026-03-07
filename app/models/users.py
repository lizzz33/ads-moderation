from pydantic import BaseModel


class UserModel(BaseModel):
    id: int
    name: str
    password: str
    email: str
    is_active: bool = True


class CreateUserInDto(BaseModel):
    name: str
    password: str
    email: str


class LoginUserInDto(BaseModel):
    login: str
    password: str
