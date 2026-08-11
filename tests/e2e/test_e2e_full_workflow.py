import pytest


@pytest.mark.e2e
def test_e2e_full_user_portfolio_workflow(api_client, mocked_external_apis):
    # Step 1: Health check
    root_res = api_client.get("/")
    assert root_res.status_code == 200
    assert root_res.json()["message"] == "Welcome to SGSKBackend!"

    # Step 2: Fetch share lots for US Stocks
    sheet_res = api_client.get("/share-lot/sheet/us-stock")
    assert sheet_res.status_code == 200
    sheet_data = sheet_res.json()
    assert "summaries" in sheet_data

    # Extract symbols for price lookup
    symbols = [s["symbol"] for s in sheet_data["summaries"]]
    assert "AAPL" in symbols

    # Step 3: Fetch market prices and FX rates for the portfolio symbols
    payload = {
        "summaries": [{"symbol": sym, "assetType": "us-stock"} for sym in symbols]
    }
    price_res = api_client.post("/price/fetch-prices", json=payload)
    assert price_res.status_code == 200
    price_data = price_res.json()

    assert "prices" in price_data
    assert "rate" in price_data
    assert "AAPL" in price_data["prices"]
    assert price_data["prices"]["AAPL"]["price"] == 185.50
