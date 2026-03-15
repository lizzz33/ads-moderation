import sys
from http import HTTPStatus

import jwt
import pytest
from fastapi.testclient import TestClient

from app.errors import UserNotFoundError
from app.models.users import UserModel

PASSWORD = "qwerty"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_user(async_client, mock_user_repository):
    """Тест создания пользователя (юнит)"""
    expected_user = UserModel(
        id=1,
        name="Иванов И.И.",
        login="test@example.com",
        password="hash",
        is_blocked=False,
    )
    mock_user_repository.create.return_value = expected_user

    response = await async_client.post(
        "/users/",
        json={
            "name": "Иванов И.И.",
            "login": "test@example.com",
            "password": PASSWORD,
        },
    )

    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["name"] == "Иванов И.И."
    assert data["id"] > 0
    mock_user_repository.create.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_block_user(async_client, mock_user_repository):
    """Тест блокировки пользователя (юнит)"""

    print("JWT module path:", sys.modules.get("jwt"))
    print("JWT version:", getattr(jwt, "__version__", "unknown"))
    user_id = 1

    mock_user_repository.get_by_login_and_password.return_value = UserModel(
        id=user_id,
        name="Иванов И.И.",
        login="test@example.com",
        password="hash",
        is_blocked=False,
    )

    login_response = await async_client.post(
        "/login", json={"login": "test@example.com", "password": PASSWORD}
    )

    assert login_response.status_code == HTTPStatus.OK
    token = login_response.json()["access_token"]

    mock_user_repository.block.return_value = UserModel(
        id=user_id,
        name="Иванов И.И.",
        login="test@example.com",
        password="hash",
        is_blocked=True,
    )

    response = await async_client.patch(
        f"/users/block/{user_id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["id"] == user_id
    assert data["is_blocked"] is True
    mock_user_repository.block.assert_called_once_with(user_id)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_user(async_client, mock_user_repository):
    """Тест удаления пользователя (юнит)"""
    user_id = 1

    mock_user_repository.get_by_login_and_password.return_value = UserModel(
        id=user_id,
        name="Иванов И.И.",
        login="test@example.com",
        password="hash",
        is_blocked=False,
    )

    expected_user = UserModel(
        id=user_id,
        name="Иванов И.И.",
        login="test@example.com",
        password="hash",
        is_blocked=False,
    )
    mock_user_repository.delete.return_value = expected_user

    login_response = await async_client.post(
        "/login", json={"login": "test@example.com", "password": PASSWORD}
    )
    token = login_response.json()["access_token"]

    response = await async_client.delete(
        f"/users/{user_id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["id"] == user_id
    mock_user_repository.delete.assert_called_once_with(user_id)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_many_users(async_client, mock_user_repository):
    """Тест получения списка пользователей (юнит)"""
    user_id = 1

    mock_user_repository.get_by_login_and_password.return_value = UserModel(
        id=user_id,
        name="Иванов И.И.",
        login="test@example.com",
        password="hash",
        is_blocked=False,
    )

    expected_users = [
        UserModel(id=1, name="User 1", login="user1@test.com", password="hash", is_blocked=False),
        UserModel(id=2, name="User 2", login="user2@test.com", password="hash", is_blocked=False),
    ]
    mock_user_repository.get_many.return_value = expected_users

    login_response = await async_client.post(
        "/login", json={"login": "test@example.com", "password": PASSWORD}
    )
    token = login_response.json()["access_token"]

    response = await async_client.get("/users/", headers={"Authorization": f"Bearer {token}"})

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
        id=user_id,
        name="Иванов И.И.",
        login="test@example.com",
        password="hash",
        is_blocked=False,
    )
    mock_user_repository.get_by_login_and_password.return_value = expected_user

    response = await async_client.post(
        "/login", json={"login": "test@example.com", "password": PASSWORD}
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    mock_user_repository.get_by_login_and_password.assert_called_once_with(
        "test@example.com", PASSWORD
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_user_integration(db_connection, async_client):
    """Интеграционный тест создания пользователя"""
    response = await async_client.post(
        "/users/",
        json={"name": "Иванов И.И.", "login": "test@example.com", "password": PASSWORD},
    )

    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    user_id = data["id"]

    result = await db_connection.fetchrow("SELECT * FROM account WHERE id = $1", user_id)
    assert result is not None
    assert result["name"] == "Иванов И.И."
    assert result["login"] == "test@example.com"
    assert result["is_blocked"] is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_block_user_integration(db_connection, async_client, test_user):
    """Интеграционный тест блокировки пользователя"""
    user_id = test_user["id"]

    login_response = await async_client.post(
        "/login", json={"login": test_user["login"], "password": PASSWORD}
    )

    assert login_response.status_code == HTTPStatus.OK
    token = login_response.json()["access_token"]

    response = await async_client.patch(
        f"/users/block/{user_id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == HTTPStatus.OK

    result = await db_connection.fetchrow("SELECT is_blocked FROM account WHERE id = $1", user_id)
    assert result["is_blocked"] is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_token(async_client: TestClient, mock_user_repository):
    """Тест получения JWT токена (юнит)"""
    user_id = 1
    expected_user = UserModel(
        id=user_id,
        name="Иванов И.И.",
        login="test@example.com",
        password="hash",
        is_blocked=False,
    )
    mock_user_repository.get_by_login_and_password.return_value = expected_user

    response = await async_client.post(
        "/login", json={"login": "test@example.com", "password": PASSWORD}
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    mock_user_repository.get_by_login_and_password.assert_called_once_with(
        "test@example.com", PASSWORD
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_invalid_credentials(async_client: TestClient, mock_user_repository):
    """Тест неверных данных при входе"""
    mock_user_repository.get_by_login_and_password.side_effect = UserNotFoundError

    response = await async_client.post(
        "/login", json={"login": "wrong@test.com", "password": "wrong"}
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_current_user_with_token(async_client: TestClient, mock_user_repository):
    """Тест получения текущего пользователя по токену"""
    user_id = 1
    expected_user = UserModel(
        id=user_id,
        name="Иванов И.И.",
        login="test@example.com",
        password="hash",
        is_blocked=False,
    )

    mock_user_repository.get_by_login_and_password.return_value = expected_user
    mock_user_repository.get.return_value = expected_user

    login_response = await async_client.post(
        "/login", json={"login": "test@example.com", "password": PASSWORD}
    )
    token = login_response.json()["access_token"]

    response = await async_client.get(
        "/users/current", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["id"] == user_id


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_current_user_invalid_token(async_client: TestClient):
    """Тест с невалидным токеном"""
    response = await async_client.get(
        "/users/current", headers={"Authorization": "Bearer invalid.token.here"}
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_current_user_no_token(async_client: TestClient):
    """Тест без токена"""
    response = await async_client.get("/users/current")
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_user_by_id_with_token(async_client: TestClient, mock_user_repository):
    """Тест получения пользователя по ID с токеном"""
    user_id = 2
    expected_user = UserModel(
        id=user_id,
        name="Петров П.П.",
        login="petrov@test.com",
        password="hash",
        is_blocked=False,
    )

    mock_user_repository.get_by_login_and_password.return_value = UserModel(
        id=1,
        name="Иванов И.И.",
        login="test@example.com",
        password="hash",
        is_blocked=False,
    )
    mock_user_repository.get.return_value = expected_user

    login_response = await async_client.post(
        "/login", json={"login": "test@example.com", "password": PASSWORD}
    )
    token = login_response.json()["access_token"]

    response = await async_client.get(
        f"/users/{user_id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["id"] == user_id


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cannot_block_another_user(async_client, mock_user_repository):
    """Тест: нельзя заблокировать другого пользователя"""
    user_id = 1
    another_user_id = 2

    mock_user_repository.get_by_login_and_password.return_value = UserModel(
        id=user_id,
        name="Иванов И.И.",
        login="test@example.com",
        password="hash",
        is_blocked=False,
    )

    login_response = await async_client.post(
        "/login", json={"login": "test@example.com", "password": PASSWORD}
    )
    token = login_response.json()["access_token"]

    response = await async_client.patch(
        f"/users/block/{another_user_id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    mock_user_repository.block.assert_not_called()
