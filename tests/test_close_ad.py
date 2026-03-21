from http import HTTPStatus
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from app.repositories.ads import AdsRepository


@pytest.mark.unit
def test_close_ad_success_unit(app_client: TestClient, mock_ads_repository, auth_token):
    """Тест успешного закрытия объявления"""
    mock_ads_repository.get_ad_by_id.return_value = {
        "item_id": 123,
        "is_closed": False,
        "seller_id": 1,
    }
    mock_ads_repository.close_ad.return_value = True

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = app_client.post("/close", json={"item_id": 123}, headers=headers)

    assert response.status_code == HTTPStatus.OK


@pytest.mark.unit
def test_close_ad_not_found_unit(app_client: TestClient, mock_ads_repository, auth_token):
    """Тест закрытия несуществующего объявления"""
    mock_ads_repository.get_ad_by_id.return_value = None

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = app_client.post("/close", json={"item_id": 999}, headers=headers)

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.unit
def test_close_ad_twice_unit(app_client: TestClient, mock_ads_repository, auth_token):
    """Тест повторного закрытия объявления"""
    mock_ads_repository.get_ad_by_id.side_effect = [
        {"item_id": 123, "is_closed": False, "seller_id": 1},
        {"item_id": 123, "is_closed": True, "seller_id": 1},
    ]
    mock_ads_repository.close_ad.return_value = True

    headers = {"Authorization": f"Bearer {auth_token}"}
    first = app_client.post("/close", json={"item_id": 123}, headers=headers)
    assert first.status_code == HTTPStatus.OK


@pytest.mark.unit
def test_close_ad_db_error_unit(app_client: TestClient, mock_ads_repository, auth_token):
    """Тест ошибки БД"""
    from fastapi import HTTPException

    mock_ads_repository.get_ad_by_id.side_effect = HTTPException(
        status_code=503, detail="Сервис базы данных временно недоступен"
    )

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = app_client.post("/close", json={"item_id": 123}, headers=headers)

    assert response.status_code == 503


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_ad_caches_unit(mock_request):
    """Тест удаления кэшей при закрытии объявления"""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [{"id": 1}, {"id": 2}]

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_conn
    mock_context.__aexit__.return_value = None

    mock_pool = Mock()
    mock_pool.acquire.return_value = mock_context

    mock_request.app.state.pg_pool = mock_pool

    repo = AdsRepository(request=mock_request)

    await repo.delete_ad_caches(123)

    assert mock_request.app.state.redis_storage.delete.call_count == 3
    mock_conn.fetch.assert_called_once()
    assert mock_conn.fetch.call_args[0][1] == 123


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ads_repository_close_ad_integration(test_ad, mock_request_with_db):
    """Интеграционный тест закрытия объявления в БД"""
    repo = AdsRepository(request=mock_request_with_db)

    initial = await repo.get_ad_by_id(test_ad)
    assert initial is not None
    assert initial["is_closed"] is False

    result = await repo.close_ad(test_ad)
    assert result is True

    updated = await repo.get_ad_by_id(test_ad)
    assert updated["is_closed"] is True

    for_moderation = await repo.get_ad_for_moderation(test_ad)
    assert for_moderation is None

    result_again = await repo.close_ad(test_ad)
    assert result_again is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simple_predict_with_real_db(async_client, test_ad, auth_token):
    """Интеграционный тест simple_predict с реальной БД"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = await async_client.post(
        "/simple_predict", json={"item_id": test_ad}, headers=headers
    )

    assert response.status_code == HTTPStatus.OK


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_close_flow_integration(async_client, test_ad, auth_token):
    """Полный интеграционный тест: simple_predict -> close -> simple_predict"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    predict_before = await async_client.post(
        "/simple_predict", json={"item_id": test_ad}, headers=headers
    )
    assert predict_before.status_code == HTTPStatus.OK
