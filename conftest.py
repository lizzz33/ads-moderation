import asyncio
import uuid
from http import HTTPStatus
from typing import Any, Generator, Mapping
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from app.clients.postgres import get_pg_connection
from app.main import app
from app.model import load_or_train_model


@pytest.fixture
def event_loop():
    """Фикстура для event loop в асинхронных тестах"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


class MockPool:
    """Мок для пула соединений PostgreSQL"""

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
def mock_kafka():
    """Мок для Kafka продюсера"""
    producer = AsyncMock()
    producer.send_moderation_request = AsyncMock()
    producer.send_json = AsyncMock()
    return producer


@pytest.fixture
def mock_user_repository():
    """Мок для UserRepository в unit тестах"""
    from unittest.mock import AsyncMock

    from app.repositories.users import UserRepository

    mock_repo = AsyncMock(spec=UserRepository)

    with patch("app.routers.users.user_service") as mock_service:
        mock_service.user_repo = mock_repo
        mock_service.register = mock_repo.create
        mock_service.get = mock_repo.get
        mock_service.get_many = mock_repo.get_many
        mock_service.deactivate = mock_repo.update
        mock_service.delete = mock_repo.delete
        mock_service.login = mock_repo.get_by_login_and_password

        yield mock_repo


@pytest.fixture
def mock_ads_repository():
    """Мок для AdsRepository в unit тестах"""
    from unittest.mock import AsyncMock

    from app.repositories.ads import AdsRepository

    mock_repo = AsyncMock(spec=AdsRepository)

    mock_repo.get_ad_for_moderation.return_value = {
        "item_id": 123,
        "name": "Test Ad",
        "description": "Test Description",
        "category": 1,
        "images_qty": 3,
        "seller_id": 1,
        "is_verified_seller": True,
        "username": "test_seller",
        "email": "seller@test.com",
    }

    mock_repo.get_ad_id.return_value = 123
    mock_repo.get_ad_by_id.return_value = {
        "item_id": 123,
        "name": "Test Ad",
        "description": "Test Description",
        "category": 1,
        "images_qty": 3,
        "is_verified_seller": True,
        "seller_id": 1,
        "is_closed": False,
    }

    mock_repo.close_ad.return_value = True
    mock_repo.delete_ad_caches.return_value = None

    with patch("app.routers.moderation.AdsRepository") as mock_ads_class:
        mock_ads_class.return_value = mock_repo
        yield mock_repo


@pytest.fixture
def mock_moderation_repository():
    """Мок для ModerationRepository в unit тестах"""
    from unittest.mock import AsyncMock

    from app.repositories.moderation import ModerationRepository

    mock_repo = AsyncMock(spec=ModerationRepository)

    mock_repo.create_task.return_value = 1
    mock_repo.mark_task_failed.return_value = None
    mock_repo.get_task_result.return_value = {
        "task_id": 1,
        "status": "completed",
        "is_violation": False,
        "probability": 0.1,
    }

    with patch("app.routers.moderation.ModerationRepository") as mock_moderation_class:
        mock_moderation_class.return_value = mock_repo
        yield mock_repo


@pytest.fixture
def app_client(db_connection) -> Generator[TestClient, None, None]:
    """Синхронный тестовый клиент с подключением к БД"""
    app.state.model = load_or_train_model()
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = None
    app.state.redis_storage = mock_redis
    app.state.pg_pool = MockPool(db_connection)

    yield TestClient(app)

    app.state.model = None
    app.state.redis_storage = None
    app.state.pg_pool = None


@pytest.fixture
def app_client_without_model():
    """Тестовый клиент без загруженной модели"""
    model = app.state.model
    app.state.model = None
    mock_redis = AsyncMock()
    app.state.pg_pool = None
    mock_redis.get.return_value = None
    mock_redis.set.return_value = None
    app.state.redis_storage = mock_redis

    try:
        client = TestClient(app)
        yield client
    finally:
        app.state.model = model
        app.state.redis_storage = None
        app.state.pg_pool = None


@pytest.fixture
async def async_client(db_connection):
    """Асинхронный тестовый клиент"""
    app.state.model = load_or_train_model()
    app.state.kafka_producer = AsyncMock()
    app.state.kafka_producer.send_moderation_request = AsyncMock()
    app.state.pg_pool = MockPool(db_connection)
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = None
    app.state.redis_storage = mock_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.state.model = None
    app.state.kafka_producer = None
    app.state.pg_pool = None
    app.state.redis_storage = None


@pytest.fixture
async def async_client_without_kafka(db_connection):
    """Асинхронный тестовый клиент без Kafka"""
    app.state.model = load_or_train_model()
    app.state.kafka_producer = None
    app.state.pg_pool = MockPool(db_connection)
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = None
    app.state.redis_storage = mock_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.state.model = None
    app.state.kafka_producer = None
    app.state.pg_pool = None
    app.state.redis_storage = None


@pytest.fixture
async def redis_client():
    """Фикстура для прямого доступа к Redis в тестах"""
    from app.clients.redis import get_redis_connection

    async with get_redis_connection() as conn:
        yield conn
        await conn.flushdb()


@pytest.fixture
def mock_request():
    """Создает мок объекта Request для тестирования"""
    request = Mock(spec=Request)
    request.app = Mock()
    request.app.state = Mock()
    request.app.state.model = Mock()
    request.app.state.redis_storage = AsyncMock()
    request.app.state.kafka_producer = AsyncMock()
    return request


@pytest.fixture
def mock_request_with_db(db_connection, mock_request):
    """Расширенная версия mock_request с подключением к БД"""
    mock_request.app.state.pg_pool = MockPool(db_connection)
    return mock_request


@pytest.fixture
def base_ad_data():
    """Базовые данные для создания объявления"""
    return {
        "seller_id": 1,
        "is_verified_seller": False,
        "item_id": 100,
        "name": "Тест",
        "description": "Тест",
        "category": 1,
        "images_qty": 0,
    }


@pytest.fixture(scope="function")
def some_user(
    app_client: TestClient,
    name: str,
    password: str,
) -> Generator[Mapping[str, Any], None, None]:
    """Создание и удаление тестового пользователя"""
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


@pytest_asyncio.fixture
async def db_connection():
    """Соединение с БД с очисткой таблиц"""
    async with get_pg_connection() as conn:
        # Очистка перед тестом
        await conn.execute("DELETE FROM moderation_results")
        await conn.execute("DELETE FROM advertisement")
        await conn.execute("DELETE FROM sellers")
        await conn.execute("DELETE FROM account")

        yield conn

        # Очистка после теста
        await conn.execute("DELETE FROM moderation_results")
        await conn.execute("DELETE FROM advertisement")
        await conn.execute("DELETE FROM sellers")
        await conn.execute("DELETE FROM account")


@pytest.fixture
async def test_user(db_connection):
    """Создание тестового пользователя"""
    user_id = await db_connection.fetchval(
        """
        INSERT INTO account (name, password, email, is_active)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        "Иванов И.И.",
        "hash",
        "test@example.com",
        True,
    )
    return {"id": user_id, "name": "Иванов И.И.", "email": "test@example.com"}


@pytest.fixture
async def test_seller(db_connection):
    """Создание тестового продавца"""
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
    """Создание тестового объявления"""
    item_id = await db_connection.fetchval(
        """
        INSERT INTO advertisement 
        (seller_id, name, description, category, images_qty, is_closed)
        VALUES ($1, $2, $3, $4, $5, $6) 
        RETURNING item_id
        """,
        test_seller,
        "Test Ad",
        "Description",
        1,
        3,
        False,
    )
    return item_id


@pytest.fixture
async def test_task(db_connection, test_ad):
    """Создание тестовой задачи модерации"""
    task_id = await db_connection.fetchval(
        """
        INSERT INTO moderation_results (item_id, status) 
        VALUES ($1, 'pending') 
        RETURNING id
        """,
        test_ad,
    )
    return task_id
