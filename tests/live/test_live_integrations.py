import httpx
import pytest

from config.sheet_config import SHEET_CONFIG, get_sheet_export_url
from services.price_service import PriceService
from services.share_lot_service import ShareLotService


@pytest.mark.live_e2e
@pytest.mark.asyncio
async def test_live_google_sheet_csv_connectivity():
    """Verify live connectivity to published Google Sheets CSV export."""
    gid = SHEET_CONFIG["gids"]["us-stock"]
    url = get_sheet_export_url(gid)
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        res = await client.get(url)
        assert res.status_code == 200
        assert "Symbol" in res.text
        assert "Quantity" in res.text

@pytest.mark.live_e2e
@pytest.mark.asyncio
async def test_live_yahoo_finance_price_fetch():
    """Verify live HTTP lookup against Yahoo Finance API."""
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
        price_service = PriceService(client=client)
        rate = await price_service.fetch_exchange_rate("USD", "THB")
        assert isinstance(rate, float)
        assert rate > 20.0  # Sanity check for USD/THB rate range


@pytest.mark.live_e2e
@pytest.mark.asyncio
async def test_live_share_lot_service_fetch():
    """Verify ShareLotService live fetch and FIFO parsing."""
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
        service = ShareLotService(client=client)
        result = await service.fetch_sheet("us-stock")
        assert result.error is None
        assert result.totalSymbols >= 0
