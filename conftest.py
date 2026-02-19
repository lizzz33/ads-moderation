import asyncio
import uuid
from http import HTTPStatus
from typing import Any, Generator, Mapping
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.clients.postgres import get_pg_connection
from app.main import app
from app.model import load_or_train_model


@pytest.fixture
def app_client() -> Generator[TestClient, None, None]:
    app.state.model = load_or_train_model()
    yield TestClient(app)
    app.state.model = None


@pytest.fixture
def app_client_without_model():
    model = app.state.model
    app.state.model = None
    try:
        client = TestClient(app)
        yield client
    finally:
        app.state.model = model


class MockPool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        class MockConnection:
            def __init__(self, conn):
                self._conn = conn

            async def __aenter__(self):
                return self._conn

            async def __aexit__(self, *args):
                pass

        return MockConnection(self._conn)


@pytest.fixture
async def async_client(db_connection):
    app.state.model = load_or_train_model()
    app.state.kafka_producer = AsyncMock()
    app.state.kafka_producer.send_moderation_request = AsyncMock()
    app.state.pg_pool = MockPool(db_connection)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.state.model = None
    app.state.kafka_producer = None
    app.state.pg_pool = None


@pytest.fixture
async def async_client_without_kafka(db_connection):
    app.state.model = load_or_train_model()
    app.state.kafka_producer = None
    app.state.pg_pool = MockPool(db_connection)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.state.model = None
    app.state.kafka_producer = None
    app.state.pg_pool = None


@pytest.fixture
def mock_kafka():
    producer = AsyncMock()
    producer.send_moderation_request = AsyncMock()
    producer.send_json = AsyncMock()
    return producer


@pytest.fixture(scope="function")
def some_user(
    app_client: TestClient,
    name: str,
    password: str,
) -> Generator[Mapping[str, Any], None, None]:
    create_response = app_client.post(
        "/users",
        json=dict(name=name, password=password, email=f"user_{uuid.uuid4().hex[:10]}@example.com"),
    )
    created_user = create_response.json()
    assert create_response.status_code == HTTPStatus.CREATED

    yield created_user

    deleted_response = app_client.delete(
        f"/users/{created_user['id']}",
        cookies={"x-user-id": str(created_user["id"])},
    )
    assert deleted_response.status_code in (HTTPStatus.OK, HTTPStatus.NOT_FOUND)


@pytest.fixture
def base_ad_data():
    return {
        "seller_id": 1,
        "is_verified_seller": False,
        "item_id": 100,
        "name": "Тест",
        "description": "Тест",
        "category": 1,
        "images_qty": 0,
    }


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_connection():
    async with get_pg_connection() as conn:
        # УБИРАЕМ transaction() - данные будут видны всем соединениям
        await conn.execute("DELETE FROM moderation_results")
        await conn.execute("DELETE FROM advertisement")
        await conn.execute("DELETE FROM sellers")
        await conn.execute("DELETE FROM account")

        yield conn

        # Очищаем после теста (если нужно)
        await conn.execute("DELETE FROM moderation_results")
        await conn.execute("DELETE FROM advertisement")
        await conn.execute("DELETE FROM sellers")
        await conn.execute("DELETE FROM account")


@pytest.fixture
async def test_seller(db_connection):
    seller_id = await db_connection.fetchval(
        """
        INSERT INTO sellers (username, email, password, is_verified) 
        VALUES ($1, $2, $3, $4) 
        RETURNING seller_id
        """,
        "test_seller",
        "seller@test.com",
        "hash",
        True,
    )
    return seller_id


@pytest.fixture
async def test_ad(db_connection, test_seller):
    item_id = await db_connection.fetchval(
        """
        INSERT INTO advertisement 
        (seller_id, name, description, category, images_qty)
        VALUES ($1, $2, $3, $4, $5) 
        RETURNING item_id
        """,
        test_seller,
        "Test Ad",
        "Description",
        1,
        3,
    )
    return item_id


@pytest.fixture
async def test_task(db_connection, test_ad):
    """Создаёт тестовую задачу модерации"""
    task_id = await db_connection.fetchval(
        "INSERT INTO moderation_results (item_id, status) VALUES ($1, 'pending') RETURNING id",
        test_ad,
    )
    return task_id
