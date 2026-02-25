import os

from dotenv import load_dotenv

load_dotenv()

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
TOPIC = os.getenv("TOPIC", "moderation")
DLQ_TOPIC = os.getenv("DLQ_TOPIC", "moderation_dlq")
CONSUMER_GROUP = os.getenv("CONSUMER_GROUP", "moderation-worker")

API_PORT = int(os.getenv("API_PORT", "8003"))

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "moderation")
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = os.getenv("DB_PORT", "5432")

PG_DSN = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY_SECONDS = int(os.getenv("RETRY_DELAY_SECONDS", "5"))

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_TTL = int(os.getenv("REDIS_TTL_DAYS", 1)) * 24 * 60 * 60  # TTL для кэша пользователей
REDIS_TTL_PREDICTION = int(
    os.getenv("REDIS_TTL_PREDICTION", 3600)
)  # TTL для предсказаний (в секундах)
