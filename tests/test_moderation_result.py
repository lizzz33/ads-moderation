from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.exceptions import HTTPException

from app.models.ads import AdSimpleRequest, ModerationResultResponse
from app.repositories.moderation import ModerationRepository
from app.routers.moderation import async_predict, get_moderation_result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_moderation_result_returns_cached(mock_request, mock_current_user):
    """Тест: результат возвращается из кэша"""
    cached_data = {
        "task_id": 123,
        "status": "completed",
        "is_violation": True,
        "probability": 0.87,
    }

    mock_request.app.state.redis_storage.get.return_value = cached_data

    result = await get_moderation_result(123, mock_request, mock_current_user)

    mock_request.app.state.redis_storage.get.assert_called_once_with("moderation_result:123")
    assert isinstance(result, ModerationResultResponse)
    assert result.task_id == 123
    assert result.status == "completed"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_moderation_result_goes_to_db_when_cache_miss(mock_request, mock_current_user):
    """Тест: при отсутствии в кэше данные берутся из БД"""
    db_data = {"task_id": 123, "status": "completed", "is_violation": False, "probability": 0.23}

    mock_request.app.state.redis_storage.get.return_value = None
    mock_request.app.state.redis_storage.set.return_value = None

    with patch("app.routers.moderation.ModerationRepository") as MockModerationRepo:
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_task_result.return_value = db_data
        MockModerationRepo.return_value = mock_repo_instance

        result = await get_moderation_result(123, mock_request, mock_current_user)

        mock_request.app.state.redis_storage.get.assert_called_once_with("moderation_result:123")
        mock_repo_instance.get_task_result.assert_called_once_with(123)
        mock_request.app.state.redis_storage.set.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_moderation_result_not_found(mock_request, mock_current_user):
    """Тест: 404 если задачи нет"""
    mock_request.app.state.redis_storage.get.return_value = None

    with patch("app.routers.moderation.ModerationRepository") as MockModerationRepo:
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_task_result.return_value = None
        MockModerationRepo.return_value = mock_repo_instance

        with pytest.raises(HTTPException) as exc_info:
            await get_moderation_result(999, mock_request, mock_current_user)

        assert exc_info.value.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_moderation_result_pending_not_cached(mock_request, mock_current_user):
    """Тест: pending статус не кэшируется"""
    pending_data = {"task_id": 123, "status": "pending", "is_violation": None, "probability": None}

    mock_request.app.state.redis_storage.get.return_value = None

    with patch("app.routers.moderation.ModerationRepository") as MockModerationRepo:
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_task_result.return_value = pending_data
        MockModerationRepo.return_value = mock_repo_instance

        result = await get_moderation_result(123, mock_request, mock_current_user)

        mock_request.app.state.redis_storage.set.assert_not_called()
        assert result.status == "pending"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_moderation_result_db_error(mock_request, mock_current_user):
    """Тест: 500 при ошибке БД"""
    mock_request.app.state.redis_storage.get.return_value = None

    with patch("app.routers.moderation.ModerationRepository") as MockModerationRepo:
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_task_result.side_effect = Exception("DB error")
        MockModerationRepo.return_value = mock_repo_instance

        with pytest.raises(HTTPException) as exc_info:
            await get_moderation_result(123, mock_request, mock_current_user)

        assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_predict_success_unit(
    mock_request, mock_current_user, mock_ads_repository, mock_moderation_repository
):
    """Тест: успешный запуск асинхронного предсказания"""
    mock_request.app.state.kafka_producer = AsyncMock()
    mock_request.app.state.kafka_producer.send_moderation_request = AsyncMock()

    mock_ads_repository.get_ad_id.return_value = 456
    mock_moderation_repository.create_task.return_value = 789

    with (
        patch("app.routers.moderation.AdsRepository", return_value=mock_ads_repository),
        patch(
            "app.routers.moderation.ModerationRepository", return_value=mock_moderation_repository
        ),
    ):
        ad_request = AdSimpleRequest(item_id=123)
        response = await async_predict(ad_request, mock_request, mock_current_user)

        assert response.task_id == 789
        assert response.status == "pending"
        mock_ads_repository.get_ad_id.assert_called_once_with(123)
        mock_moderation_repository.create_task.assert_called_once_with(456)
        mock_request.app.state.kafka_producer.send_moderation_request.assert_called_once_with(456)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_predict_ad_not_found_unit(
    mock_request, mock_current_user, mock_ads_repository
):
    """Тест: объявление не найдено"""
    mock_ads_repository.get_ad_id.return_value = None

    with patch("app.routers.moderation.AdsRepository", return_value=mock_ads_repository):
        ad_request = AdSimpleRequest(item_id=999)

        with pytest.raises(HTTPException) as exc_info:
            await async_predict(ad_request, mock_request, mock_current_user)

        assert exc_info.value.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_task(db_connection, test_ad, mock_request_with_db):
    """Интеграционный тест создания задачи модерации"""
    repo = ModerationRepository(request=mock_request_with_db)
    task_id = await repo.create_task(test_ad)

    assert task_id is not None
    assert isinstance(task_id, int)

    result = await db_connection.fetchrow(
        "SELECT * FROM moderation_results WHERE id = $1", task_id
    )
    assert result is not None
    assert result["item_id"] == test_ad
    assert result["status"] == "pending"
    assert result["is_violation"] is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_task_result(db_connection, test_task, mock_request_with_db):
    """Интеграционный тест получения результата задачи"""
    repo = ModerationRepository(request=mock_request_with_db)

    await db_connection.execute(
        """
        UPDATE moderation_results 
        SET status = 'completed', is_violation = TRUE, probability = 0.95
        WHERE id = $1
        """,
        test_task,
    )

    result = await repo.get_task_result(test_task)

    assert result is not None
    assert result["task_id"] == test_task
    assert result["status"] == "completed"
    assert result["is_violation"] is True
    assert result["probability"] == 0.95


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_task_result_not_found(mock_request_with_db):
    """Интеграционный тест получения несуществующей задачи"""
    repo = ModerationRepository(request=mock_request_with_db)
    result = await repo.get_task_result(999999)
    assert result is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mark_task_failed(db_connection, test_task, mock_request_with_db):
    """Интеграционный тест отметки задачи как ошибочной"""
    repo = ModerationRepository(request=mock_request_with_db)
    error_msg = "Test error message"

    await repo.mark_task_failed(test_task, error_msg)

    result = await db_connection.fetchrow(
        "SELECT * FROM moderation_results WHERE id = $1", test_task
    )
    assert result["status"] == "failed"
    assert result["error_message"] == error_msg


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_flow(db_connection, test_ad, mock_request_with_db):
    """Интеграционный тест полного цикла: создать и получить"""
    repo = ModerationRepository(request=mock_request_with_db)

    task_id = await repo.create_task(test_ad)
    assert task_id is not None

    await db_connection.execute(
        "UPDATE moderation_results SET status = 'completed' WHERE id = $1",
        task_id,
    )

    result = await repo.get_task_result(task_id)
    assert result["status"] == "completed"
