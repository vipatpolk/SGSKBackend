import pytest

from models.transaction import PriceData
from services.price_service import PriceService


@pytest.fixture
def service():
    return PriceService()


@pytest.mark.unit
def test_resolve_crypto_price(service):
    tickers = [
        {"symbol": "BTCTHB", "price": "3000000.00"},
        {"symbol": "BTCUSDT", "price": "90000.00"},
        {"symbol": "ETHTHB", "price": "100000.00"},
    ]

    price, currency = service._resolve_crypto_price("BTC.CRYPTO", tickers)
    assert price == 3000000.00
    assert currency == "THB"

    price, currency = service._resolve_crypto_price("ETH.CRYPTO", tickers)
    assert price == 100000.00
    assert currency == "THB"

    price, currency = service._resolve_crypto_price("UNKNOWN.CRYPTO", tickers)
    assert price == 0.0
    assert currency == ""


@pytest.mark.unit
def test_is_crypto_and_fund_helpers(service):
    assert service._is_crypto({"symbol": "BTC.CRYPTO"}) is True
    assert service._is_crypto({"assetType": "crypto", "symbol": "BTC"}) is True
    assert service._is_crypto({"symbol": "AAPL"}) is False

    assert service._is_fund({"symbol": "K-CHANGE.BKFUND"}) is True
    assert service._is_fund({"assetType": "mutual-fund", "symbol": "K-CHANGE"}) is True
    assert service._is_fund({"symbol": "AAPL"}) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_exchange_rate_same_currency(service):
    rate = await service.fetch_exchange_rate("USD", "USD")
    assert rate == 1.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_stock_prices_mocked(service, monkeypatch):
    async def mock_fetch_single_stock(symbol: str):
        if symbol == "AAPL":
            return "AAPL", PriceData(symbol="AAPL", name="Apple Inc.", price=180.50, currency="USD")
        return symbol, PriceData(symbol=symbol, name="", price=0.0, currency="")

    monkeypatch.setattr(service, "_fetch_single_stock", mock_fetch_single_stock)

    price_map = await service.fetch_stock_prices(["AAPL", "INVALID_SYM"])
    assert "AAPL" in price_map
    assert price_map["AAPL"].price == 180.50
    assert price_map["AAPL"].name == "Apple Inc."
    assert "INVALID_SYM" not in price_map
