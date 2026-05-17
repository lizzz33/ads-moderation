"""Тесты: async_predict — kafka failure, worker — shutdown / no task_id"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.ads import AdSimpleRequest
from app.workers.moderation_worker import handle_error


# ── async_predict: kafka send fails → 500 ─────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_predict_kafka_send_fails_500(mock_request, mock_current_user):
    from app.routers.moderation import async_predict

    mock_kafka = AsyncMock()
    mock_kafka.send_moderation_request.side_effect = Exception("Kafka connection lost")
    mock_request.app.state.kafka_producer = mock_kafka

    mock_ads_repo = AsyncMock()
    mock_ads_repo.get_ad_id.return_value = 123

    mock_moderation_repo = AsyncMock()
    mock_moderation_repo.create_task.return_value = 456

    with (
        patch("app.routers.moderation.AdsRepository", return_value=mock_ads_repo),
        patch("app.routers.moderation.ModerationRepository", return_value=mock_moderation_repo),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await async_predict(AdSimpleRequest(item_id=123), mock_request, mock_current_user)

        assert exc_info.value.status_code == 500
        mock_moderation_repo.mark_task_failed.assert_called_once()


# ── worker: handle_error — producer.send_json падает ──────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_handle_error_producer_send_fails():
    mock_producer = AsyncMock()
    mock_producer.send_json.side_effect = Exception("DLQ down")
    mock_conn = AsyncMock()

    event = {"item_id": 1, "retry_count": 3}

    # не должно падать, ошибка логируется
    await handle_error(mock_producer, mock_conn, event, "Test error", task_id=123)

    mock_producer.send_json.assert_called_once()
    # task should still be marked failed
    mock_conn.execute.assert_called_once()


# ── worker: shutdown_event прерывает цикл ─────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_worker_shutdown_on_event():
    from app.workers import moderation_worker

    mock_msg = AsyncMock()
    mock_msg.value = {"item_id": 1, "task_id": 1, "retry_count": 0}

    mock_consumer = AsyncMock()

    # Эмулируем: первый message обрабатывается, потом shutdown
    call_count = 0

    async def fake_aiter(self):
        nonlocal call_count
        yield mock_msg
        call_count += 1

    mock_consumer.__aiter__ = fake_aiter
    mock_consumer.commit = AsyncMock()
    mock_consumer.stop = AsyncMock()

    mock_producer = AsyncMock()
    mock_producer.stop = AsyncMock()

    with patch("app.workers.moderation_worker.AIOKafkaConsumer", return_value=mock_consumer):
        with patch("app.workers.moderation_worker.KafkaProducer") as MockProd:
            MockProd.return_value = mock_producer
            with patch("app.workers.moderation_worker.load_or_train_model", return_value=MagicMock()):
                with patch("app.workers.moderation_worker.get_pg_connection") as mock_pg:
                    mock_conn = AsyncMock()
                    mock_conn.fetchrow.return_value = {
                        "is_verified_seller": True,
                        "images_qty": 5,
                        "description": "test",
                        "category": 1,
                    }
                    mock_conn.execute = AsyncMock()

                    mock_ctx = AsyncMock()
                    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
                    mock_ctx.__aexit__ = AsyncMock(return_value=None)
                    mock_pg.return_value = mock_ctx

                    # Set shutdown event before running
                    moderation_worker.shutdown_event.set()

                    try:
                        await moderation_worker.main()
                    except StopAsyncIteration:
                        pass

    # cleanup
    moderation_worker.shutdown_event.clear()


# ── worker: сообщение без task_id, pending задача найдена ─────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_worker_message_without_task_id(db_connection, test_ad, test_task):
    from app.workers import moderation_worker

    mock_msg = AsyncMock()
    mock_msg.value = {"item_id": test_ad, "retry_count": 0}
    # no task_id in event

    mock_consumer = AsyncMock()

    async def fake_aiter(self):
        yield mock_msg

    mock_consumer.__aiter__ = fake_aiter
    mock_consumer.commit = AsyncMock()
    mock_consumer.stop = AsyncMock()

    mock_producer = AsyncMock()
    mock_producer.stop = AsyncMock()

    with patch("app.workers.moderation_worker.AIOKafkaConsumer", return_value=mock_consumer):
        with patch("app.workers.moderation_worker.KafkaProducer") as MockProd:
            MockProd.return_value = mock_producer
            with patch("app.workers.moderation_worker.load_or_train_model", return_value=MagicMock()):
                with patch("app.workers.moderation_worker.get_prediction", return_value=0.7):
                    try:
                        await moderation_worker.main()
                    except StopAsyncIteration:
                        pass

    result = await db_connection.fetchrow(
        "SELECT status, is_violation, probability FROM moderation_results WHERE id = $1",
        test_task,
    )
    assert result["status"] == "completed"
    assert result["is_violation"] is True
    assert result["probability"] == 0.7

    moderation_worker.shutdown_event.clear()
