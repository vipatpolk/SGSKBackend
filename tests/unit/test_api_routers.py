import pytest

from models.transaction import PriceData, SheetResult


@pytest.mark.unit
def test_root_endpoint(api_client):
    res = api_client.get("/")
    assert res.status_code == 200
    json_data = res.json()
    assert "message" in json_data
    assert json_data["message"] == "Welcome to SGSKBackend!"

@pytest.mark.unit
def test_get_share_lot_invalid_tab(api_client):
    res = api_client.get("/share-lot/sheet/non-existent-tab")
    assert res.status_code == 200
    data = res.json()
    assert "error" in data
    assert "Invalid tab id" in data["error"]

@pytest.mark.unit
def test_get_share_lot_valid_tab_mocked(api_client, monkeypatch):
    async def mock_fetch_sheet(self, tab_id: str):
        return SheetResult(
            summaries=[],
            closedSummaries=[],
            transactionSummaries=[],
            rawTransactions=[],
            totalCostByCurrency={"USD": 1000.0},
            totalProceedsByCurrency={},
            totalRealizedPLByCurrency={},
            totalSymbols=1,
            totalLots=1,
            isClosed=False
        )

    from services.share_lot_service import ShareLotService
    monkeypatch.setattr(ShareLotService, "fetch_sheet", mock_fetch_sheet)

    res = api_client.get("/share-lot/sheet/us-stock")
    assert res.status_code == 200
    data = res.json()
    assert data["totalCostByCurrency"]["USD"] == 1000.0
    assert data["totalSymbols"] == 1

@pytest.mark.unit
def test_fetch_prices_endpoint_mocked(api_client, monkeypatch):
    async def mock_fetch_prices_and_rate(self, summaries):
        return {
            "prices": {
                "AAPL": PriceData(symbol="AAPL", name="Apple Inc.", price=185.0, currency="USD").model_dump()
            },
            "rate": 35.5
        }

    from services.price_service import PriceService
    monkeypatch.setattr(PriceService, "fetch_prices_and_rate", mock_fetch_prices_and_rate)

    res = api_client.post("/price/fetch-prices", json={"summaries": [{"symbol": "AAPL", "assetType": "us-stock"}]})
    assert res.status_code == 200
    data = res.json()
    assert "prices" in data
    assert "rate" in data
    assert data["rate"] == 35.5
    assert data["prices"]["AAPL"]["price"] == 185.0

@pytest.mark.unit
def test_usd_thb_rate_endpoint_mocked(api_client, monkeypatch):
    async def mock_fetch_exchange_rate(self, from_curr="USD", to_curr="THB"):
        return 35.75

    from services.price_service import PriceService
    monkeypatch.setattr(PriceService, "fetch_exchange_rate", mock_fetch_exchange_rate)

    res = api_client.get("/price/exchange-rate?from_currency=USD&to_currency=THB")
    assert res.status_code == 200
    data = res.json()
    assert data["rate"] == 35.75
