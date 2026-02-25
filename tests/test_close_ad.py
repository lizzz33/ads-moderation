from http import HTTPStatus
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from app.repositories.ads import AdsRepository


@pytest.mark.unit
def test_close_ad_success_unit(app_client: TestClient, mock_ads_repository):
    """Тест успешного закрытия объявления"""
    mock_ads_repository.get_ad_by_id.return_value = {
        "item_id": 123,
        "is_closed": False,
        "seller_id": 1,
    }
    mock_ads_repository.close_ad.return_value = True

    response = app_client.post("/close", json={"item_id": 123})

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["success"] is True
    assert data["item_id"] == 123
    assert "успешно закрыто" in data["message"]

    mock_ads_repository.get_ad_by_id.assert_called_once_with(123)
    mock_ads_repository.close_ad.assert_called_once_with(123)


@pytest.mark.unit
def test_close_ad_not_found_unit(app_client: TestClient, mock_ads_repository):
    """Тест закрытия несуществующего объявления"""
    mock_ads_repository.get_ad_by_id.return_value = None

    response = app_client.post("/close", json={"item_id": 999})

    assert response.status_code == HTTPStatus.NOT_FOUND
    mock_ads_repository.get_ad_by_id.assert_called_once_with(999)
    mock_ads_repository.close_ad.assert_not_called()


@pytest.mark.unit
def test_close_ad_twice_unit(app_client: TestClient, mock_ads_repository):
    """Тест повторного закрытия объявления"""
    mock_ads_repository.get_ad_by_id.side_effect = [
        {"item_id": 123, "is_closed": False, "seller_id": 1},
        {"item_id": 123, "is_closed": True, "seller_id": 1},
    ]
    mock_ads_repository.close_ad.return_value = True

    first = app_client.post("/close", json={"item_id": 123})
    assert first.status_code == HTTPStatus.OK
    assert "успешно закрыто" in first.json()["message"]

    second = app_client.post("/close", json={"item_id": 123})
    assert second.status_code == HTTPStatus.OK
    assert "уже было закрыто" in second.json()["message"]

    mock_ads_repository.close_ad.assert_called_once_with(123)


@pytest.mark.unit
def test_close_ad_db_error_unit(app_client: TestClient, mock_ads_repository):
    """Тест ошибки БД"""
    from fastapi import HTTPException

    mock_ads_repository.get_ad_by_id.side_effect = HTTPException(
        status_code=503, detail="Сервис базы данных временно недоступен"
    )

    response = app_client.post("/close", json={"item_id": 123})

    assert response.status_code == 503


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_ad_caches_unit(mock_request):
    """Тест удаления кэшей при закрытии объявления"""
    mock_redis = AsyncMock()
    mock_redis.delete = AsyncMock()

    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [{"id": 1}, {"id": 2}]

    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [{"id": 1}, {"id": 2}]

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_conn
    mock_context.__aexit__.return_value = None

    mock_pool = Mock()
    mock_pool.acquire.return_value = mock_context

    mock_request.app.state.pg_pool = mock_pool

    repo = AdsRepository(request=mock_request)

    await repo.delete_ad_caches(123, mock_redis)

    assert mock_redis.delete.call_count == 3
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
async def test_simple_predict_with_real_db(async_client, test_ad):
    """Интеграционный тест simple_predict с реальной БД"""
    response = await async_client.post("/simple_predict", json={"item_id": test_ad})

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert "is_violation" in data
    assert "probability" in data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_close_flow_integration(async_client, test_ad):
    """Полный интеграционный тест: simple_predict -> close -> simple_predict"""
    predict_before = await async_client.post("/simple_predict", json={"item_id": test_ad})
    assert predict_before.status_code == HTTPStatus.OK

    close_response = await async_client.post("/close", json={"item_id": test_ad})
    assert close_response.status_code == HTTPStatus.OK

    predict_after = await async_client.post("/simple_predict", json={"item_id": test_ad})
    assert predict_after.status_code == HTTPStatus.NOT_FOUND
