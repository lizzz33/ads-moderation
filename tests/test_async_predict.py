import pytest


@pytest.mark.asyncio
async def test_async_predict_creates_task(async_client, test_ad):
    response = await async_client.post("/async_predict", json={"item_id": test_ad})
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_async_predict_not_found(async_client):
    response = await async_client.post("/async_predict", json={"item_id": 999999})
    assert response.status_code == 404


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


@pytest.mark.asyncio
async def test_async_predict_without_kafka(async_client_without_kafka, test_ad):
    response = await async_client_without_kafka.post("/async_predict", json={"item_id": test_ad})
    assert response.status_code == 503
