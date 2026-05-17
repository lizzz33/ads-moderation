import pytest
from http import HTTPStatus
from unittest.mock import AsyncMock, patch

from app.repositories.ads import AdsRepository
from app.services.auth import hash_password
from conftest import PASSWORD


@pytest.fixture(scope="module")
def hashed_password():
    return hash_password(PASSWORD)


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_data",
    [
        {"item_id": "не число"},
        {"ad_id": 1},
        {},
        {"item_id": None},
        [],
        None,
    ],
)
async def test_simple_predict_validation(async_client, auth_token, invalid_data):
    """Тест валидации входных данных"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = await async_client.post("/simple_predict", json=invalid_data, headers=headers)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.unit
@pytest.mark.asyncio
async def test_simple_predict_seller_not_found(async_client, auth_token):
    """Тест ситуации, когда продавец не найден"""
    mock_repo = AsyncMock(spec=AdsRepository)
    mock_repo.get_ad_for_moderation.return_value = None

    with patch("app.routers.moderation.AdsRepository", return_value=mock_repo):
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = await async_client.post(
            "/simple_predict", json={"item_id": 999999}, headers=headers
        )

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simple_predict_with_join(async_client, test_ad, auth_token):
    """Интеграционный тест simple_predict с существующим объявлением"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = await async_client.post(
        "/simple_predict", json={"item_id": test_ad}, headers=headers
    )
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert "is_violation" in data
    assert "probability" in data
    assert 0 <= data["probability"] <= 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simple_predict_logic(db_connection, async_client, auth_token, hashed_password):
    """Интеграционный тест логики simple_predict с реальными данными"""

    async def create_test_seller_and_ad(conn):
        seller_id = await conn.fetchval(
            """
            INSERT INTO sellers (username, email, password, is_verified)
            VALUES ($1, $2, $3, $4)
            RETURNING seller_id
            """,
            "test_user",
            "test@example.com",
            hashed_password,
            True,
        )

        item_id = await conn.fetchval(
            """
            INSERT INTO advertisement
            (seller_id, name, description, category, images_qty, is_closed)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING item_id
            """,
            seller_id,
            "Test Ad",
            "Test description",
            1,
            5,
            False,
        )
        return item_id

    item_id = await create_test_seller_and_ad(db_connection)

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = await async_client.post(
        "/simple_predict", json={"item_id": item_id}, headers=headers
    )
    assert response.status_code == HTTPStatus.OK

    json_data = response.json()
    assert "is_violation" in json_data
    assert "probability" in json_data
    assert 0 <= json_data["probability"] <= 1
    assert json_data["is_violation"] == (json_data["probability"] >= 0.5)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "is_verified, images_qty, category, description_length",
    [
        (True, 5, 1, 100),
        (False, 10, 50, 500),
        (False, 0, 99, 10),
        (True, 0, 1, 5000),
    ],
)
async def test_simple_predict_various_cases(
    db_connection, async_client, is_verified, images_qty, category, description_length, auth_token,
    hashed_password,
):
    """Параметризированный интеграционный тест с разными комбинациями данных"""

    async def create_test_case(conn):
        seller_id = await conn.fetchval(
            """
            INSERT INTO sellers (username, email, password, is_verified)
            VALUES ($1, $2, $3, $4)
            RETURNING seller_id
            """,
            f"user_{is_verified}_{category}_{description_length}",
            f"user_{is_verified}_{category}_{description_length}@test.com",
            hashed_password,
            is_verified,
        )

        description = "x" * description_length if description_length > 0 else ""

        item_id = await conn.fetchval(
            """
            INSERT INTO advertisement
            (seller_id, name, description, category, images_qty, is_closed)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING item_id
            """,
            seller_id,
            f"Test Ad {category}",
            description,
            category,
            images_qty,
            False,
        )
        return item_id

    item_id = await create_test_case(db_connection)

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = await async_client.post(
        "/simple_predict", json={"item_id": item_id}, headers=headers
    )
    assert response.status_code == HTTPStatus.OK

    result = response.json()
    assert isinstance(result["is_violation"], bool)
    assert isinstance(result["probability"], float)
