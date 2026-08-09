import pytest
from services.nav_service import NavService
from models.transaction import PriceData

@pytest.fixture
def service():
    return NavService()

@pytest.mark.asyncio
async def test_fetch_fund_navs_empty(service):
    res = await service.fetch_fund_navs([])
    assert res == {}

@pytest.mark.asyncio
async def test_fetch_single_fund_nav_not_found(service, monkeypatch):
    # Mock fetch_fund_profile returning None (fund not found)
    async def mock_fetch_fund_profile(clean_symbol: str, sym_upper: str):
        return None

    monkeypatch.setattr(service, "fetch_fund_profile", mock_fetch_fund_profile)

    res = await service.fetch_single_fund_nav("UNKNOWN_FUND.BKFUND")
    assert res["originalSymbol"] == "UNKNOWN_FUND.BKFUND"
    assert res["data"].price == 0.0
    assert res["data"].currency == "THB"

@pytest.mark.asyncio
async def test_fetch_single_fund_nav_success(service, monkeypatch):
    # Mock profile lookup
    async def mock_fetch_fund_profile(clean_symbol: str, sym_upper: str):
        return {
            "proj_id": "M0123_2560",
            "proj_name_en": "K-CHANGE MUTUAL FUND",
            "fund_class_name": "main"
        }

    # Mock NAV data lookup
    async def mock_fetch_fund_nav_data(symbol: str, clean_symbol: str, sym_upper: str, fund: dict):
        return {
            "originalSymbol": symbol,
            "data": PriceData(symbol=symbol, name=fund["name"], price=15.75, currency="THB")
        }

    monkeypatch.setattr(service, "fetch_fund_profile", mock_fetch_fund_profile)
    monkeypatch.setattr(service, "fetch_fund_nav_data", mock_fetch_fund_nav_data)

    res = await service.fetch_single_fund_nav("K-CHANGE.BKFUND")
    assert res["originalSymbol"] == "K-CHANGE.BKFUND"
    assert res["data"].price == 15.75
    assert res["data"].name == "K-CHANGE MUTUAL FUND"
    assert res["data"].currency == "THB"
