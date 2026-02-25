import pytest


@pytest.mark.unit
@pytest.mark.parametrize(
    "bad_data",
    [
        {"item_id": "не число"},
        {},
        {"wrong_field": 1},
        None,
    ],
)
@pytest.mark.asyncio
async def test_async_predict_validation(async_client, bad_data):
    response = await async_client.post("/async_predict", json=bad_data)
    assert response.status_code == 422


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_predict_not_found(async_client):
    response = await async_client.post("/async_predict", json={"item_id": 999999})
    assert response.status_code == 404


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_predict_without_kafka(async_client_without_kafka, mock_ads_repository):
    mock_item_id = 999
    mock_ads_repository.get_ad_id.return_value = mock_item_id
    response = await async_client_without_kafka.post(
        "/async_predict", json={"item_id": mock_item_id}
    )
    assert response.status_code == 503


@pytest.mark.integration
@pytest.mark.asyncio
async def test_async_predict_creates_task(db_connection, async_client, test_ad, mock_kafka):
    response = await async_client.post("/async_predict", json={"item_id": test_ad})
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "pending"

    task_id = data["task_id"]
    result = await db_connection.fetchrow(
        "SELECT * FROM moderation_results WHERE id = $1", task_id
    )
    assert result is not None
    assert result["item_id"] == test_ad
    assert result["status"] == "pending"
