import asyncio
from http import HTTPStatus
from typing import Any, Generator, Mapping

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from clients.postgres import get_pg_connection
from main import app
from model import load_or_train_model


@pytest.fixture
def app_client() -> Generator[TestClient, None, None]:
    app.state.model = load_or_train_model()
    return TestClient(app)


@pytest.fixture
def app_client_without_model():
    model = app.state.model
    app.state.model = None

    try:
        client = TestClient(app)
        yield client
    finally:
        app.state.model = model


@pytest.fixture(scope="function")
def some_user(
    app_client: TestClient,
    name: str,
    password: str,
) -> Generator[Mapping[str, Any], None, None]:
    create_response = app_client.post(
        "/users",
        json=dict(
            name=name,
            password=password,
            email=f"{name.lower().replace('.', '_').replace(' ', '_')}@example.com",
        ),
    )
    created_user = create_response.json()

    assert create_response.status_code == HTTPStatus.CREATED
    yield created_user

    deleted_response = app_client.delete(
        f"/users/{created_user['id']}",
        cookies={"x-user-id": str(created_user["id"])},
    )
    assert (
        deleted_response.status_code == HTTPStatus.OK
        or deleted_response.status_code == HTTPStatus.NOT_FOUND
    )


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
    """Создает event loop для всех тестов"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_connection():
    """Асинхронная фикстура для подключения к БД"""
    async with get_pg_connection() as conn:
        # Очищаем перед использованием
        await conn.execute("DELETE FROM advertisement")
        await conn.execute("DELETE FROM account")
        yield conn
        # Очищаем после использования
        await conn.execute("DELETE FROM advertisement")
        await conn.execute("DELETE FROM account")
