from unittest.mock import AsyncMock, patch

import pytest

from app.workers.moderation_worker import MAX_RETRIES, handle_error, main


@pytest.mark.integration
@pytest.mark.asyncio
async def test_worker_processes_message_successfully(db_connection, test_ad, test_task):
    """Интеграционный тест успешной обработки сообщения воркером"""
    mock_msg = AsyncMock()
    mock_msg.value = {"item_id": test_ad, "task_id": test_task, "retry_count": 0}

    mock_consumer = AsyncMock()
    mock_consumer.__aiter__.return_value = [mock_msg]

    with patch("app.workers.moderation_worker.AIOKafkaConsumer", return_value=mock_consumer):
        with patch("app.workers.moderation_worker.KafkaProducer") as MockProducer:
            mock_producer = AsyncMock()
            MockProducer.return_value = mock_producer

            try:
                await main()
            except StopAsyncIteration:
                pass

    result = await db_connection.fetchrow(
        "SELECT status, is_violation, probability FROM moderation_results WHERE id = $1", test_task
    )
    assert result["status"] == "completed"
    assert result["is_violation"] is not None
    assert result["probability"] is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_worker_handles_missing_ad(db_connection, test_task):
    """Интеграционный тест обработки сообщения с несуществующим объявлением"""
    mock_msg = AsyncMock()
    mock_msg.value = {
        "item_id": 999999,
        "task_id": test_task,
        "retry_count": MAX_RETRIES - 1,
    }

    mock_consumer = AsyncMock()
    mock_consumer.__aiter__.return_value = [mock_msg]

    with patch("app.workers.moderation_worker.AIOKafkaConsumer", return_value=mock_consumer):
        with patch("app.workers.moderation_worker.KafkaProducer") as MockProducer:
            mock_producer = AsyncMock()
            MockProducer.return_value = mock_producer

            try:
                await main()
            except StopAsyncIteration:
                pass

    result = await db_connection.fetchrow(
        "SELECT status FROM moderation_results WHERE id = $1", test_task
    )
    assert result["status"] == "failed"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_worker_retry_mechanism(test_ad, test_task):
    """Юнит-тест механизма повторных попыток при ошибке"""
    mock_msg = AsyncMock()
    mock_msg.value = {"item_id": test_ad, "task_id": test_task, "retry_count": 0}

    mock_consumer = AsyncMock()
    mock_consumer.__aiter__.return_value = [mock_msg, mock_msg, mock_msg]

    mock_producer = AsyncMock()

    with patch("app.workers.moderation_worker.AIOKafkaConsumer", return_value=mock_consumer):
        with patch("app.workers.moderation_worker.KafkaProducer", return_value=mock_producer):
            with patch(
                "app.workers.moderation_worker.get_prediction", side_effect=Exception("ML Error")
            ):
                try:
                    await main()
                except StopAsyncIteration:
                    pass

    assert mock_producer.send_json.call_count > 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_worker_sends_to_dlq_after_max_retries(test_ad, test_task):
    """Юнит-тест отправки в DLQ после превышения максимальных попыток"""
    mock_msg = AsyncMock()
    mock_msg.value = {
        "item_id": test_ad,
        "task_id": test_task,
        "retry_count": MAX_RETRIES - 1,
    }

    mock_consumer = AsyncMock()
    mock_consumer.__aiter__.return_value = [mock_msg]

    mock_producer = AsyncMock()

    with patch("app.workers.moderation_worker.AIOKafkaConsumer", return_value=mock_consumer):
        with patch("app.workers.moderation_worker.KafkaProducer", return_value=mock_producer):
            with patch(
                "app.workers.moderation_worker.get_prediction", side_effect=Exception("ML Error")
            ):
                try:
                    await main()
                except StopAsyncIteration:
                    pass

    assert mock_producer.send_json.called
    call_args = mock_producer.send_json.call_args[0]
    assert call_args[0] == "moderation_dlq"
    assert "error" in call_args[1]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_handle_error_function():
    """Юнит-тест функции обработки ошибок"""
    mock_producer = AsyncMock()
    mock_conn = AsyncMock()

    event = {"item_id": 1, "task_id": 123}
    error_msg = "Test error"
    task_id = 123

    await handle_error(mock_producer, mock_conn, event, error_msg, task_id)

    mock_producer.send_json.assert_called_once()

    mock_conn.execute.assert_called_once()
    assert "UPDATE moderation_results" in mock_conn.execute.call_args[0][0]
    assert "failed" in mock_conn.execute.call_args[0][0]
