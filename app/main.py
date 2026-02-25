import logging
import os
from contextlib import asynccontextmanager

import asyncpg
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from app.clients.kafka import KafkaProducer
from app.clients.settings import KAFKA_BOOTSTRAP, PG_DSN
from app.model import load_or_train_model
from app.repositories.users import UserRedisStorage
from app.routers.moderation import (
    async_predict_router,
    close_ad_router,
    moderation_result_router,
    predict_router,
    simple_predict_router,
)
from app.routers.users import root_router
from app.routers.users import router as user_router

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model = load_or_train_model(use_mlflow=os.environ["USE_MLFLOW"])

    app.state.kafka_producer = KafkaProducer(KAFKA_BOOTSTRAP)
    await app.state.kafka_producer.start()
    app.state.pg_pool = await asyncpg.create_pool(PG_DSN, min_size=1, max_size=10)

    app.state.redis_storage = UserRedisStorage()
    yield

    await app.state.kafka_producer.stop()


app = FastAPI(lifespan=lifespan, title="Сервис модерации объявлений")


@app.get("/")
async def root():
    return {"message": "Hello World"}


app.include_router(user_router, prefix="/users")
app.include_router(predict_router)
app.include_router(simple_predict_router)
app.include_router(root_router)
app.include_router(async_predict_router)
app.include_router(moderation_result_router)
app.include_router(close_ad_router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
