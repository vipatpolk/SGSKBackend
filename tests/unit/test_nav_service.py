import pytest

from models.transaction import PriceData
from services.nav_service import NavService


@pytest.fixture
def service():
    return NavService()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_fund_navs_empty(service):
    res = await service.fetch_fund_navs([])
    assert res == {}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_single_fund_nav_not_found(service, monkeypatch):
    async def mock_fetch_fund_profile(clean_symbol: str, sym_upper: str):
        return None

    monkeypatch.setattr(service, "fetch_fund_profile", mock_fetch_fund_profile)

    res = await service.fetch_single_fund_nav("UNKNOWN_FUND.FUND")
    assert res["originalSymbol"] == "UNKNOWN_FUND.FUND"
    assert res["data"].price == 0.0
    assert res["data"].currency == "THB"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_single_fund_nav_success(service, monkeypatch):
    async def mock_fetch_fund_profile(clean_symbol: str, sym_upper: str):
        return {"proj_id": "M0123_2560", "proj_name_en": "K-CHANGE MUTUAL FUND", "fund_class_name": "main"}

    async def mock_fetch_fund_nav_data(symbol: str, clean_symbol: str, sym_upper: str, fund: dict):
        return {
            "originalSymbol": symbol,
            "data": PriceData(symbol=symbol, name=fund["name"], price=15.75, currency="THB"),
        }

    monkeypatch.setattr(service, "fetch_fund_profile", mock_fetch_fund_profile)
    monkeypatch.setattr(service, "fetch_fund_nav_data", mock_fetch_fund_nav_data)

    res = await service.fetch_single_fund_nav("K-CHANGE.FUND")
    assert res["originalSymbol"] == "K-CHANGE.FUND"
    assert res["data"].price == 15.75
    assert res["data"].name == "K-CHANGE MUTUAL FUND"
    assert res["data"].currency == "THB"

    res_bk = await service.fetch_single_fund_nav("K-CHANGE.BKFUND")
    assert res_bk["originalSymbol"] == "K-CHANGE.BKFUND"
    assert res_bk["data"].price == 15.75


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_pvd_policies_success(service, monkeypatch):
    class MockResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return [
                {
                    "sub_policy_id": "PVDSP500",
                    "sub_policy_name": "นโยบายกองทุนรวมต่างประเทศ หุ้นยูเอส",
                    "policy_name": "ตราสารทุน",
                    "aimc_type": "EQUS",
                    "risk_level": "RS6",
                    "objective": "ลงทุนในกองทุนเปิดไทยพาณิชย์หุ้นยูเอส",
                }
            ]

    async def mock_get(url, *args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(service.client, "get", mock_get)

    res = await service.fetch_pvd_policies("V0001_2553")
    assert "PVDSP500" in res
    assert res["PVDSP500"]["name"] == "นโยบายกองทุนรวมต่างประเทศ หุ้นยูเอส"
    assert res["PVDSP500"]["policyName"] == "ตราสารทุน"
    assert res["PVDSP500"]["aimcType"] == "EQUS"
    assert res["PVDSP500"]["riskLevel"] == "RS6"

