from http import HTTPStatus

import pytest


@pytest.mark.asyncio
async def test_simple_predict_with_join(async_client, test_ad):
    response = await async_client.post("/simple_predict", json={"item_id": test_ad})
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert "is_violation" in data
    assert "probability" in data
    assert 0 <= data["probability"] <= 1


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
    response = app_client.post("/simple_predict", json=invalid_data)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_simple_predict_logic(app_client, db_connection):

    async def create_test_seller_and_ad(conn):
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

        item_id = await conn.fetchval(
            """
            INSERT INTO advertisement 
            (seller_id, name, description, category, images_qty)
            VALUES ($1, $2, $3, $4, $5) 
            RETURNING item_id
            """,
            seller_id,
            "Test Ad",
            "Test description",
            1,
            5,
        )
        return item_id

    item_id = await create_test_seller_and_ad(db_connection)

    response = app_client.post("/simple_predict", json={"item_id": item_id})
    assert response.status_code == HTTPStatus.OK

    json_data = response.json()
    assert "is_violation" in json_data
    assert "probability" in json_data
    assert 0 <= json_data["probability"] <= 1
    assert json_data["is_violation"] == (json_data["probability"] >= 0.5)


def test_simple_predict_without_model(app_client_without_model):
    response = app_client_without_model.post("/simple_predict", json={"item_id": 1})
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE


@pytest.mark.parametrize(
    "is_verified, images_qty, category, description_length",
    [
        (True, 5, 1, 100),  # Верифицированный продавец
        (False, 10, 50, 500),  # Неверифицированный, много картинок
        (False, 0, 99, 10),  # Неверифицированный, без картинок
        (True, 0, 1, 5000),  # Верифицированный, длинное описание
    ],
)
@pytest.mark.asyncio
async def test_simple_predict_various_cases(
    app_client, db_connection, is_verified, images_qty, category, description_length
):

    async def create_test_case(conn):
        seller_id = await conn.fetchval(
            """
            INSERT INTO sellers (username, email, password, is_verified) 
            VALUES ($1, $2, $3, $4) 
            RETURNING seller_id
            """,
            f"user_{is_verified}",
            f"user_{category}@test.com",
            "hash",
            is_verified,
        )

        description = "x" * description_length if description_length > 0 else ""

        item_id = await conn.fetchval(
            """
            INSERT INTO advertisement 
            (seller_id, name, description, category, images_qty)
            VALUES ($1, $2, $3, $4, $5) 
            RETURNING item_id
            """,
            seller_id,
            f"Test Ad {category}",
            description,
            category,
            images_qty,
        )
        return item_id

    item_id = await create_test_case(db_connection)

    response = app_client.post("/simple_predict", json={"item_id": item_id})
    assert response.status_code == HTTPStatus.OK

    result = response.json()
    assert isinstance(result["is_violation"], bool)
    assert isinstance(result["probability"], float)


@pytest.mark.asyncio
async def test_simple_predict_seller_not_found(async_client):
    response = await async_client.post("/simple_predict", json={"item_id": 999999})
    assert response.status_code == HTTPStatus.NOT_FOUND
