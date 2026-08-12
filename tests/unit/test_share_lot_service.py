import pytest

from models.transaction import SheetResult
from services.share_lot_service import ShareLotService


@pytest.fixture
def service():
    return ShareLotService()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_sheet_invalid_tab(service):
    res = await service.fetch_sheet("invalid-tab-id")
    assert isinstance(res, SheetResult)
    assert res.error is not None
    assert "Invalid tab id" in res.error

@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_sheet_mocked_http(service, monkeypatch, fixture_us_stock_csv):
    class MockResponse:
        status_code = 200
        text = fixture_us_stock_csv
        def raise_for_status(self): pass

    async def mock_get(url, *args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(service.client, "get", mock_get)

    res = await service.fetch_sheet("us-stock")
    assert res.error is None
    assert res.totalSymbols == 2
    assert "USD" in res.totalCostByCurrency

@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_closed_position_sheet_mocked(service, monkeypatch, sample_csv_closed_position):
    class MockResponse:
        status_code = 200
        text = sample_csv_closed_position
        def raise_for_status(self): pass

    async def mock_get(url, *args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(service.client, "get", mock_get)

    res = await service.fetch_sheet("closed-position")
    assert res.isClosed is True
    assert res.totalSymbols == 1
    assert "USD" in res.totalRealizedPLByCurrency
    assert res.totalRealizedPLByCurrency["USD"] == 500.0

@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_all_sheets_mocked(service, monkeypatch, fixture_us_stock_csv):
    class MockResponse:
        status_code = 200
        text = fixture_us_stock_csv
        def raise_for_status(self): pass

    async def mock_get(url, *args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(service.client, "get", mock_get)

    res = await service.fetch_all_sheets()
    assert res.isClosed is False
    assert res.totalSymbols > 0
