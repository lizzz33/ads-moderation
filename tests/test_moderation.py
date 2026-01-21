from http import HTTPStatus


def test_verified_seller_passes(app_client, base_ad_data):
    """Верифицированный продавец всегда проходит"""
    data = base_ad_data.copy()
    data["is_verified_seller"] = True
    response = app_client.post("/predict", json=data)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["is_allowed"]


def test_unverified_seller_with_images_passes(app_client, base_ad_data):
    """Неверифицированный продавец с картинками проходит"""
    data = base_ad_data.copy()
    data["is_verified_seller"] = False
    data["images_qty"] = 3
    response = app_client.post("/predict", json=data)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["is_allowed"]


def test_unverified_seller_no_images_fails(app_client, base_ad_data):
    """Неверифицированный продавец без картинок не проходит"""
    data = base_ad_data.copy()
    data["is_verified_seller"] = False
    data["images_qty"] = 0
    response = app_client.post("/predict", json=data)
    assert response.status_code == HTTPStatus.OK
    assert not response.json()["is_allowed"]


def test_validation_error_wrong_type(app_client):
    """Ошибка валидации при неправильном типе"""
    response = app_client.post("/predict", json={"seller_id": "не число"})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_validation_missing_field(app_client, base_ad_data):
    """Ошибка валидации при отсутствии поля"""
    data = base_ad_data.copy()
    del data["seller_id"]  # Удаляем обязательное поле
    response = app_client.post("/predict", json=data)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
