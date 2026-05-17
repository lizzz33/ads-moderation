from http import HTTPStatus

import pytest


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "is_verified_seller, images_qty",
    [
        (True, 0),
        (False, 3),
        (False, 0),
    ],
)
async def test_allowed_ad(async_client, base_ad_data, is_verified_seller, images_qty, auth_token):
    data = base_ad_data.copy()
    data["is_verified_seller"] = is_verified_seller
    data["images_qty"] = images_qty

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = await async_client.post("/predict", json=data, headers=headers)
    assert response.status_code == HTTPStatus.OK

    json_data = response.json()
    assert "is_violation" in json_data
    assert "probability" in json_data
    assert 0 <= json_data["probability"] <= 1


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_data",
    [
        {"seller_id": "не число"},
        {"is_verified_seller": "да"},
        {"item_id": None},
        {"images_qty": -1},
        None,
        [],
    ],
)
async def test_validation_values(async_client, invalid_data, auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = await async_client.post("/predict", json=invalid_data, headers=headers)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_violation_logic(async_client, base_ad_data, auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    result = (await async_client.post("/predict", json=base_ad_data, headers=headers)).json()
    assert result["is_violation"] == (result["probability"] >= 0.5)
