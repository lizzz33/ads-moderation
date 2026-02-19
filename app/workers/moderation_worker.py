import asyncio
import json
import logging
import os
from datetime import datetime

from aiokafka import AIOKafkaConsumer

from app.clients.kafka import KafkaProducer
from app.clients.postgres import get_pg_connection
from app.clients.settings import (
    CONSUMER_GROUP,
    DLQ_TOPIC,
    KAFKA_BOOTSTRAP,
    MAX_RETRIES,
    RETRY_DELAY_SECONDS,
    TOPIC,
)
from app.model import load_or_train_model
from app.routers.utils import get_prediction, prepare_features

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def handle_error(producer, conn, event, error_msg, task_id=None):

    dlq_message = {
        "original_message": event,
        "error": error_msg,
        "timestamp": datetime.now().isoformat(),
        "retry_count": event.get("retry_count", 1),
    }

    try:
        await producer.send_json(DLQ_TOPIC, dlq_message)
        logger.info("Отправлено в DLQ")
    except Exception as e:
        logger.error(f"Ошибка отправки в DLQ: {e}")

    if task_id:
        await conn.execute(
            "UPDATE moderation_results SET status='failed', error_message=$1 WHERE id=$2",
            error_msg,
            task_id,
        )


async def main():
    model = load_or_train_model(use_mlflow=os.getenv("USE_MLFLOW"))
    logger.info("Модель загружена")

    async with get_pg_connection() as conn:
        producer = KafkaProducer(KAFKA_BOOTSTRAP)
        await producer.start()

        consumer = AIOKafkaConsumer(
            TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            group_id=CONSUMER_GROUP,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )
        await consumer.start()
        logger.info(f"[worker] consuming {TOPIC} as group={CONSUMER_GROUP}")

        try:
            async for msg in consumer:
                try:
                    event = msg.value
                    item_id = event["item_id"]
                    task_id = event.get("task_id")
                    retry = event.get("retry_count", 0)

                    logger.info(f"item_id={item_id}, task_id={task_id}")

                    row = await conn.fetchrow(
                        """
                        SELECT 
                            s.is_verified as is_verified_seller,
                            a.images_qty,
                            a.description,
                            a.category
                        FROM advertisement a
                        JOIN sellers s ON a.seller_id = s.seller_id
                        WHERE a.item_id = $1
                        """,
                        item_id,
                    )

                    if not row:
                        raise ValueError(f"Объявление {item_id} не найдено")

                    if not task_id:
                        task_row = await conn.fetchrow(
                            """
                            SELECT id FROM moderation_results 
                            WHERE item_id = $1 AND status = 'pending'
                            ORDER BY created_at DESC
                            LIMIT 1
                            """,
                            item_id,
                        )
                        task_id = task_row["id"] if task_row else None

                    if not task_id:
                        raise ValueError(f"Нет задачи для item_id={item_id}")

                    features = prepare_features(row)
                    proba = get_prediction(model, features)
                    is_violation = proba >= 0.5

                    await conn.execute(
                        """
                        UPDATE moderation_results 
                        SET status = 'completed', 
                            is_violation = $1, 
                            probability = $2,
                            processed_at = CURRENT_TIMESTAMP
                        WHERE id = $3
                        """,
                        bool(is_violation),
                        float(proba),
                        task_id,
                    )

                    logger.info(f"is_violation={is_violation}, probability={proba:.3f}")

                    await consumer.commit()

                except Exception as e:
                    if retry < MAX_RETRIES - 1:
                        event["retry_count"] = retry + 1
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                        await producer.send_json(TOPIC, event)
                        logger.info(f"Повтор {retry + 2} для {item_id}")
                    else:
                        await handle_error(producer, conn, event, str(e), task_id)

                    await consumer.commit()

        finally:
            await consumer.stop()
            await producer.stop()


if __name__ == "__main__":
    asyncio.run(main())
