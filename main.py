import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from model import load_or_train_model
from routers.moderation import predict_router, simple_predict_router
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


app.include_router(user_router, prefix="/users")
app.include_router(predict_router)
app.include_router(simple_predict_router)
app.include_router(root_router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
