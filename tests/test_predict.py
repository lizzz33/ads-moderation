from http import HTTPStatus

import pytest

PASSWORD = "qwerty"


@pytest.mark.unit
@pytest.mark.parametrize(
    "is_verified_seller, images_qty",
    [
        (True, 0),
        (False, 3),
        (False, 0),
    ],
)
def test_allowed_ad(app_client, base_ad_data, is_verified_seller, images_qty, auth_token):
    data = base_ad_data.copy()
    data["is_verified_seller"] = is_verified_seller
    data["images_qty"] = images_qty

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = app_client.post("/predict", json=data, headers=headers)
    assert response.status_code == HTTPStatus.OK

    json_data = response.json()
    assert "is_violation" in json_data
    assert "probability" in json_data
    assert 0 <= json_data["probability"] <= 1


@pytest.mark.unit
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
def test_validation_values(app_client, invalid_data, auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = app_client.post("/predict", json=invalid_data, headers=headers)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.unit
def test_is_violation_logic(app_client, base_ad_data, auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    result = app_client.post("/predict", json=base_ad_data, headers=headers).json()
    assert result["is_violation"] == (result["probability"] >= 0.5)
