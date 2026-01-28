import logging
import os
from contextlib import asynccontextmanager

import numpy as np
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status

from model import load_or_train_model
from models.ads import AdRequest, AdResponse
from routers.users import root_router
from routers.users import router as user_router

load_dotenv()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model = load_or_train_model(use_mlflow=os.environ["USE_MLFLOW"])
    yield


app = FastAPI(lifespan=lifespan, title="Сервис модерации объявлений")


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.post("/predict", response_model=AdResponse)
async def predict(ad: AdRequest):
    logger.info(f"Запрос: {ad}")
    model = app.state.model

    if model is None:
        logger.error("Модель не загружена")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Модель не загружена",
        )

    is_verified = 1 if ad.is_verified_seller else 0
    images_norm = min(ad.images_qty / 20.0, 1.0)
    desc_len_norm = min(len(ad.description) / 5000.0, 1.0)
    category_norm = ad.category / 100.0

    features = np.array([[is_verified, images_norm, desc_len_norm, category_norm]])

    try:
        proba = model.predict(features)[0]
    except Exception as e:
        logger.error(f"Ошибка при предсказании: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера при обработке запроса: {str(e)}",
        )

    response = AdResponse(is_violation=(proba >= 0.5), probability=proba)

    logger.info(f"Ответ: {response}")

    return response


app.include_router(user_router, prefix="/users")
app.include_router(root_router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
