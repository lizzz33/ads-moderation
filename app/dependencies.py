from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.models.token import TokenData
from app.services.auth import auth_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    return auth_service.decode_token(token)
