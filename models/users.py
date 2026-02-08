from pydantic import BaseModel


class UserModel(BaseModel):
    id: int
    name: str
    password: str
    email: str
    is_active: bool = True
