"""Дополнительные тесты: deactivate endpoint, POST /predict без auth, 404 случаи"""

from http import HTTPStatus
from unittest.mock import AsyncMock

import pytest

from app.models.users import UserModel

from conftest import PASSWORD


# ── POST /predict без авторизации ─────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_predict_without_auth(async_client):
    response = await async_client.post(
        "/predict",
        json={
            "seller_id": 1,
            "is_verified_seller": False,
            "item_id": 100,
            "name": "Test",
            "description": "desc",
            "category": 1,
            "images_qty": 0,
        },
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.unit
@pytest.mark.asyncio
async def test_simple_predict_without_auth(async_client):
    response = await async_client.post("/simple_predict", json={"item_id": 1})
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_predict_without_auth(async_client):
    response = await async_client.post("/async_predict", json={"item_id": 1})
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.unit
@pytest.mark.asyncio
async def test_close_without_auth(async_client):
    response = await async_client.post("/close", json={"item_id": 1})
    assert response.status_code == HTTPStatus.UNAUTHORIZED


# ── GET /users/ без авторизации ───────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_users_without_auth(async_client):
    response = await async_client.get("/users/")
    assert response.status_code == HTTPStatus.UNAUTHORIZED


# ── POST /predict модель не загружена ─────────────────────────────


@pytest.mark.unit
def test_predict_model_not_loaded(app_client_without_model):
    from app.services.auth import auth_service

    token = auth_service.create_access_token({"sub": "1", "login": "test@example.com"})
    response = app_client_without_model.post(
        "/predict",
        json={
            "seller_id": 1,
            "is_verified_seller": False,
            "item_id": 100,
            "name": "Test",
            "description": "desc",
            "category": 1,
            "images_qty": 0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403 or response.status_code == 503


# ── Deactivate endpoint ───────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_deactivate_own_account(async_client, mock_user_repository):
    user_id = 1
    mock_user_repository.get_by_login_and_password.return_value = UserModel(
        id=user_id,
        name="Test",
        login="test@test.com",
        password="hash",
        is_blocked=False,
    )
    mock_user_repository.update.return_value = UserModel(
        id=user_id,
        name="Test",
        login="test@test.com",
        password="hash",
        is_blocked=False,
    )

    login_resp = await async_client.post(
        "/login", json={"login": "test@test.com", "password": PASSWORD}
    )
    token = login_resp.json()["access_token"]

    response = await async_client.patch(
        f"/users/deactivate/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == HTTPStatus.OK
    mock_user_repository.update.assert_called_once_with(user_id, is_active=False)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_deactivate_another_user_forbidden(async_client, mock_user_repository):
    user_id = 1
    other_user_id = 2

    mock_user_repository.get_by_login_and_password.return_value = UserModel(
        id=user_id,
        name="Test",
        login="test@test.com",
        password="hash",
        is_blocked=False,
    )

    login_resp = await async_client.post(
        "/login", json={"login": "test@test.com", "password": PASSWORD}
    )
    token = login_resp.json()["access_token"]

    response = await async_client.patch(
        f"/users/deactivate/{other_user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


# ── 404: GET /users/current — пользователь удалён ────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_current_user_deleted_from_db(async_client, mock_user_repository):
    user_id = 1
    mock_user_repository.get_by_login_and_password.return_value = UserModel(
        id=user_id,
        name="Test",
        login="test@test.com",
        password="hash",
        is_blocked=False,
    )

    from app.errors import UserNotFoundError

    mock_user_repository.get.side_effect = UserNotFoundError()

    login_resp = await async_client.post(
        "/login", json={"login": "test@test.com", "password": PASSWORD}
    )
    token = login_resp.json()["access_token"]

    response = await async_client.get(
        "/users/current", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


# ── 404: DELETE /users/{id} — несуществующий ──────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_nonexistent_user(async_client, mock_user_repository):
    user_id = 1
    mock_user_repository.get_by_login_and_password.return_value = UserModel(
        id=user_id,
        name="Test",
        login="test@test.com",
        password="hash",
        is_blocked=False,
    )

    from app.errors import UserNotFoundError

    mock_user_repository.delete.side_effect = UserNotFoundError()

    login_resp = await async_client.post(
        "/login", json={"login": "test@test.com", "password": PASSWORD}
    )
    token = login_resp.json()["access_token"]

    response = await async_client.delete(
        f"/users/{user_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


# ── 404: GET /users/{id} — несуществующий ─────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_user_by_id_not_found(async_client, mock_user_repository):
    user_id = 1
    mock_user_repository.get_by_login_and_password.return_value = UserModel(
        id=user_id,
        name="Test",
        login="test@test.com",
        password="hash",
        is_blocked=False,
    )

    from app.errors import UserNotFoundError

    mock_user_repository.get.side_effect = UserNotFoundError()

    login_resp = await async_client.post(
        "/login", json={"login": "test@test.com", "password": PASSWORD}
    )
    token = login_resp.json()["access_token"]

    response = await async_client.get(
        f"/users/999", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


# ── POST /users/ — обязательные поля ──────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_register_missing_name(async_client):
    response = await async_client.post(
        "/users/",
        json={"login": "test@test.com", "password": PASSWORD},
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.unit
@pytest.mark.asyncio
async def test_register_missing_login(async_client):
    response = await async_client.post(
        "/users/",
        json={"name": "Test", "password": PASSWORD},
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.unit
@pytest.mark.asyncio
async def test_register_missing_password(async_client):
    response = await async_client.post(
        "/users/",
        json={"name": "Test", "login": "test@test.com"},
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
