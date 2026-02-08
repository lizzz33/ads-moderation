from http import HTTPStatus

import pytest


def test_simple_predict_not_found(app_client):
    response = app_client.post("/simple_predict", json={"item_id": 999999})
    assert response.status_code == HTTPStatus.NOT_FOUND


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

    async def create_test_ad(conn):
        user_id = await conn.fetchval(
            "INSERT INTO account (name, email, password) VALUES ($1, $2, $3) RETURNING id",
            "Test User",
            "test@example.com",
            "hash",
        )

        return await conn.fetchval(
            """
            INSERT INTO advertisement 
            (seller_id, is_verified_seller, name, description, category, images_qty)
            VALUES ($1, $2, $3, $4, $5, $6) 
            RETURNING item_id
            """,
            user_id,
            True,
            "Test Ad",
            "Test description",
            1,
            5,
        )

    item_id = await create_test_ad(db_connection)

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
    "is_verified_seller, images_qty, category, description_length",
    [
        (True, 5, 1, 100),  # Верифицированный продавец
        (False, 10, 50, 500),  # Много картинок
        (False, 0, 99, 10),  # Без картинок
        (True, 0, 1, 5000),  # Длинное описание
    ],
)
@pytest.mark.asyncio
async def test_simple_predict_various_cases(
    app_client, db_connection, is_verified_seller, images_qty, category, description_length
):

    async def create_test_case(conn):
        user_id = await conn.fetchval(
            "INSERT INTO account (name, email, password) VALUES ($1, $2, $3) RETURNING id",
            f"User_{is_verified_seller}",
            f"user_{category}@test.com",
            "hash",
        )

        description = "x" * description_length if description_length > 0 else ""

        return await conn.fetchval(
            """
            INSERT INTO advertisement 
            (seller_id, is_verified_seller, name, description, category, images_qty)
            VALUES ($1, $2, $3, $4, $5, $6) 
            RETURNING item_id
            """,
            user_id,
            is_verified_seller,
            f"Test Ad {category}",
            description,
            category,
            images_qty,
        )

    item_id = await create_test_case(db_connection)

    response = app_client.post("/simple_predict", json={"item_id": item_id})
    assert response.status_code == HTTPStatus.OK

    result = response.json()
    assert isinstance(result["is_violation"], bool)
    assert isinstance(result["probability"], float)
