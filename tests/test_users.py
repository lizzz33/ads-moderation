from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from app.models.users import UserModel

PASSWORD = "qwerty"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_user(async_client, mock_user_repository):
    """Тест создания пользователя (юнит)"""
    expected_user = UserModel(
        id=1, name="Иванов И.И.", password="hash", email="test@example.com", is_active=True
    )
    mock_user_repository.create.return_value = expected_user

    response = await async_client.post(
        "/users/", json={"name": "Иванов И.И.", "password": PASSWORD, "email": "test@example.com"}
    )

    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["name"] == "Иванов И.И."
    assert data["id"] > 0
    mock_user_repository.create.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_deactivate_user(async_client, mock_user_repository):
    """Тест деактивации пользователя (юнит)"""
    user_id = 1
    expected_user = UserModel(
        id=user_id, name="Иванов И.И.", password="hash", email="test@example.com", is_active=False
    )
    mock_user_repository.update.return_value = expected_user

    async_client.cookies.set("x-user-id", str(user_id))
    response = await async_client.patch(f"/users/deactivate/{user_id}")

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["id"] == user_id
    assert data["is_active"] is False
    mock_user_repository.update.assert_called_once_with(user_id, is_active=False)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_user(async_client, mock_user_repository):
    """Тест удаления пользователя (юнит)"""
    user_id = 1
    expected_user = UserModel(
        id=user_id, name="Иванов И.И.", password="hash", email="test@example.com", is_active=True
    )
    mock_user_repository.delete.return_value = expected_user

    async_client.cookies.set("x-user-id", str(user_id))
    response = await async_client.delete(f"/users/{user_id}")

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["id"] == user_id
    mock_user_repository.delete.assert_called_once_with(user_id)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_many_users(async_client, mock_user_repository):
    """Тест получения списка пользователей (юнит)"""
    expected_users = [
        UserModel(id=1, name="User 1", password="hash", email="user1@test.com", is_active=True),
        UserModel(id=2, name="User 2", password="hash", email="user2@test.com", is_active=True),
    ]
    mock_user_repository.get_many.return_value = expected_users

    response = await async_client.get("/users/")

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert len(data) == 2
    mock_user_repository.get_many.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_user(async_client: TestClient, mock_user_repository):
    """Тест авторизации пользователя (юнит)"""
    user_id = 1
    expected_user = UserModel(
        id=user_id, name="Иванов И.И.", password="hash", email="test@example.com", is_active=True
    )
    mock_user_repository.get_by_login_and_password.return_value = expected_user

    response = await async_client.post(
        "/login", json={"login": "test@example.com", "password": PASSWORD}
    )

    assert response.status_code == HTTPStatus.OK
    assert response.cookies.get("x-user-id") == str(user_id)
    data = response.json()
    assert data["id"] == user_id
    mock_user_repository.get_by_login_and_password.assert_called_once_with(
        "test@example.com", PASSWORD
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_current_user(async_client: TestClient, mock_user_repository):
    """Тест получения текущего пользователя (юнит)"""
    user_id = 1
    expected_user = UserModel(
        id=user_id, name="Иванов И.И.", password="hash", email="test@example.com", is_active=True
    )
    mock_user_repository.get.return_value = expected_user

    async_client.cookies.set("x-user-id", str(user_id))
    response = await async_client.get("/users/current")
    print(f"Status: {response.status_code}")
    print(f"Response body: {response.text}")

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["id"] == user_id
    mock_user_repository.get.assert_called_once_with(user_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_user_integration(db_connection, async_client):
    """Интеграционный тест создания пользователя"""
    response = await async_client.post(
        "/users/", json={"name": "Иванов И.И.", "password": PASSWORD, "email": "test@example.com"}
    )

    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    user_id = data["id"]

    result = await db_connection.fetchrow("SELECT * FROM account WHERE id = $1", user_id)
    assert result is not None
    assert result["name"] == "Иванов И.И."
    assert result["email"] == "test@example.com"


@pytest.mark.integration
async def test_deactivate_user_integration(db_connection, async_client, test_user):
    """Интеграционный тест деактивации пользователя"""
    user_id = test_user["id"]

    async_client.cookies.set("x-user-id", str(user_id))
    response = await async_client.patch(f"/users/deactivate/{user_id}")

    assert response.status_code == HTTPStatus.OK

    result = await db_connection.fetchrow("SELECT is_active FROM account WHERE id = $1", user_id)
    assert result["is_active"] is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_user_integration(db_connection, async_client, test_user):
    """Интеграционный тест удаления пользователя"""
    user_id = test_user["id"]

    async_client.cookies.set("x-user-id", str(user_id))
    response = await async_client.delete(f"/users/{user_id}")

    assert response.status_code == HTTPStatus.OK

    result = await db_connection.fetchrow("SELECT * FROM account WHERE id = $1", user_id)
    assert result is None
