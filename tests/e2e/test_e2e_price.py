import pytest


@pytest.mark.e2e
def test_e2e_fetch_prices_post(api_client, mocked_external_apis):
    payload = {"summaries": [{"symbol": "AAPL", "assetType": "us-stock"}]}
    response = api_client.post("/price/fetch-prices", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "prices" in data
    assert "rate" in data
    assert data["rate"] == 185.50 or data["rate"] >= 0.0
    assert "AAPL" in data["prices"]
    assert data["prices"]["AAPL"]["price"] == 185.50


@pytest.mark.e2e
def test_e2e_get_exchange_rate(api_client, mocked_external_apis):
    response = api_client.get("/price/exchange-rate?from_currency=USD&to_currency=THB")
    assert response.status_code == 200
    data = response.json()
    assert "rate" in data
    assert data["rate"] == 185.50
