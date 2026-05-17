"""Тесты KafkaProducer: send_json до start(), stop() без start()"""

import pytest

from app.clients.kafka import KafkaProducer


@pytest.mark.unit
@pytest.mark.asyncio
async def test_send_json_before_start_raises_runtime_error():
    producer = KafkaProducer("localhost:9092")

    with pytest.raises(RuntimeError, match="Kafka producer is not started"):
        await producer.send_json("topic", {"key": "value"})


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stop_without_start_does_not_raise():
    producer = KafkaProducer("localhost:9092")
    await producer.stop()  # не должно выбрасывать


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stop_after_start_calls_producer_stop():
    from unittest.mock import AsyncMock, patch

    with patch("app.clients.kafka.AIOKafkaProducer") as MockProducer:
        mock_instance = AsyncMock()
        MockProducer.return_value = mock_instance

        producer = KafkaProducer("localhost:9092")
        await producer.start()
        await producer.stop()

        mock_instance.stop.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_send_json_after_start_calls_send_and_wait():
    from unittest.mock import AsyncMock, patch

    with patch("app.clients.kafka.AIOKafkaProducer") as MockProducer:
        mock_instance = AsyncMock()
        MockProducer.return_value = mock_instance

        producer = KafkaProducer("localhost:9092")
        await producer.start()

        await producer.send_json("test_topic", {"item_id": 1})

        mock_instance.send_and_wait.assert_called_once()
        call_args = mock_instance.send_and_wait.call_args
        assert call_args[0][0] == "test_topic"
