from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import pytest

from app.repositories.ads import AdsRepository


@pytest.mark.unit
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
def test_simple_predict_validation(app_client, invalid_data):
    """Тест валидации некорректных данных"""
    response = app_client.post("/simple_predict", json=invalid_data)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.unit
def test_simple_predict_without_model(app_client_without_model):
    """Тест поведения при отсутствии модели"""
    response = app_client_without_model.post("/simple_predict", json={"item_id": 1})
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE


@pytest.mark.unit
@pytest.mark.asyncio
async def test_simple_predict_seller_not_found(async_client):
    """Тест ситуации, когда продавец не найден"""
    mock_repo = AsyncMock(spec=AdsRepository)
    mock_repo.get_ad_for_moderation.return_value = None

    with patch("app.routers.moderation.AdsRepository", return_value=mock_repo):
        response = await async_client.post("/simple_predict", json={"item_id": 999999})

    assert response.status_code == HTTPStatus.NOT_FOUND
    mock_repo.get_ad_for_moderation.assert_called_once_with(999999)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simple_predict_with_join(async_client, test_ad):
    """Интеграционный тест simple_predict с существующим объявлением"""
    response = await async_client.post("/simple_predict", json={"item_id": test_ad})
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert "is_violation" in data
    assert "probability" in data
    assert 0 <= data["probability"] <= 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simple_predict_logic(db_connection, async_client):
    """Интеграционный тест логики simple_predict с созданием данных"""

    async def create_test_seller_and_ad(conn):
        from app.main import app

        print(f"app.state.pg_pool: {app.state.pg_pool}")

        seller_id = await conn.fetchval(
            """
            INSERT INTO sellers (username, email, password, is_verified) 
            VALUES ($1, $2, $3, $4) 
            RETURNING seller_id
            """,
            "test_user",
            "test@example.com",
            "hash",
            True,
        )
        print(f"Создан seller_id: {seller_id}")

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

    response = await async_client.post("/simple_predict", json={"item_id": item_id})
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
    db_connection, async_client, is_verified, images_qty, category, description_length
):
    """Параметризованный интеграционный тест с разными комбинациями данных"""

    async def create_test_case(conn):
        seller_id = await conn.fetchval(
            """
            INSERT INTO sellers (username, email, password, is_verified) 
            VALUES ($1, $2, $3, $4) 
            RETURNING seller_id
            """,
            f"user_{is_verified}_{category}",
            f"user_{category}@test.com",
            "hash",
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

    response = await async_client.post("/simple_predict", json={"item_id": item_id})
    assert response.status_code == HTTPStatus.OK

    result = response.json()
    assert isinstance(result["is_violation"], bool)
    assert isinstance(result["probability"], float)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ads_repository_get_ad(test_ad, mock_request_with_db):
    """Интеграционный тест получения объявления из репозитория"""
    repo = AdsRepository(request=mock_request_with_db)

    ad = await repo.get_ad_for_moderation(test_ad)

    assert ad is not None
    assert ad["item_id"] == test_ad
    assert ad["name"] == "Test Ad"
    assert "description" in ad
    assert "category" in ad
    assert "images_qty" in ad
    assert "is_verified_seller" in ad


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ads_repository_close_ad(test_ad, mock_request_with_db):
    """Интеграционный тест закрытия объявления через репозиторий"""
    repo = AdsRepository(request=mock_request_with_db)

    initial_ad = await repo.get_ad_by_id(test_ad)
    assert initial_ad is not None
    assert initial_ad["is_closed"] is False

    result = await repo.close_ad(test_ad)
    assert result is True

    ad_for_moderation = await repo.get_ad_for_moderation(test_ad)
    assert ad_for_moderation is None

    updated_ad = await repo.get_ad_by_id(test_ad)
    assert updated_ad is not None
    assert updated_ad["is_closed"] is True

    result_again = await repo.close_ad(test_ad)
    assert result_again is False
