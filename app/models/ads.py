from typing import Optional

from pydantic import BaseModel


class AdRequest(BaseModel):
    seller_id: int
    is_verified_seller: bool
    item_id: int
    name: str
    description: str
    category: int
    images_qty: int


class AdResponse(BaseModel):
    is_violation: bool
    probability: float


class AdSimpleRequest(BaseModel):
    item_id: int


class AsyncPredictResponse(BaseModel):
    task_id: int
    status: str
    message: str


class ModerationResultResponse(BaseModel):
    task_id: int
    status: str  # pending, completed, failed
    is_violation: Optional[bool] = None
    probability: Optional[float] = None


class CloseAdRequest(BaseModel):
    item_id: int


class CloseAdResponse(BaseModel):
    success: bool
    message: str
    item_id: int
