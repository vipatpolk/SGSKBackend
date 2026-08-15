import pytest

from models.allocation import CurrencyExposure, PortfolioAllocationResponse, RebalanceRecommendation
from models.performance import PortfolioPerformanceResponse
from models.portfolio import PortfolioHoldingsResponse, PortfolioPosition, PortfolioSummary
from services.allocation_service import AllocationService
from services.performance_service import PerformanceService
from services.valuation_service import ValuationService


@pytest.mark.unit
def test_portfolio_holdings_endpoint(api_client, monkeypatch):
    async def mock_get_portfolio_holdings(self, tab_id="all", currency="THB"):
        return PortfolioHoldingsResponse(
            currency=currency,
            exchangeRate=35.0,
            tabId=tab_id,
            summary=PortfolioSummary(
                totalInvested=1000.0,
                totalValue=1200.0,
                openInvested=1000.0,
                closedInvested=0.0,
                totalUnrealizedPL=200.0,
                totalUnrealizedPLPercent=20.0,
                totalRealizedPL=0.0,
                totalRealizedPLPercent=0.0,
                totalReturn=200.0,
                totalReturnPercent=20.0,
            ),
            openPositions=[
                PortfolioPosition(
                    symbol="AAPL",
                    displaySymbol="AAPL",
                    name="Apple Inc.",
                    assetType="us-stock",
                    assetTypeLabel="U.S. Stock",
                    totalShares=10.0,
                    totalCost=1000.0,
                    averageCost=100.0,
                    currentPrice=120.0,
                    holdingValue=1200.0,
                    unrealizedPL=200.0,
                    unrealizedPLPercent=20.0,
                    currency=currency,
                    originalCurrency="USD",
                    hasPrice=True,
                    lots=[],
                )
            ],
            closedPositions=[],
        )

    monkeypatch.setattr(ValuationService, "get_portfolio_holdings", mock_get_portfolio_holdings)

    res = api_client.get("/portfolio/holdings?tab_id=all&currency=USD")
    assert res.status_code == 200
    data = res.json()
    assert data["currency"] == "USD"
    assert data["summary"]["totalValue"] == 1200.0
    assert len(data["openPositions"]) == 1
    assert data["openPositions"][0]["symbol"] == "AAPL"


@pytest.mark.unit
def test_portfolio_performance_endpoint(api_client, monkeypatch):
    async def mock_get_performance(self, timeframe="ALL", start_date=None, end_date=None, currency="THB"):
        return PortfolioPerformanceResponse(
            timeframe=timeframe,
            startDate="",
            endDate="",
            currency=currency,
            exchangeRate=35.0,
            summary=PortfolioSummary(
                totalInvested=1000.0,
                totalValue=1200.0,
                openInvested=1000.0,
                closedInvested=0.0,
                totalUnrealizedPL=200.0,
                totalUnrealizedPLPercent=20.0,
                totalRealizedPL=0.0,
                totalRealizedPLPercent=0.0,
                totalReturn=200.0,
                totalReturnPercent=20.0,
            ),
            assetTypePerformance=[],
            topGainers=[],
            topLosers=[],
            symbolPerformance=[],
        )

    monkeypatch.setattr(PerformanceService, "get_performance_analytics", mock_get_performance)

    res = api_client.get("/portfolio/performance?timeframe=YTD&currency=USD")
    assert res.status_code == 200
    data = res.json()
    assert data["timeframe"] == "YTD"
    assert data["currency"] == "USD"


@pytest.mark.unit
def test_portfolio_allocation_endpoint(api_client, monkeypatch):
    async def mock_calculate_allocation(self, targets=None, currency="THB"):
        return PortfolioAllocationResponse(
            currency=currency,
            exchangeRate=35.0,
            totalPortfolioValue=2000.0,
            recommendations=[
                RebalanceRecommendation(
                    assetType="us-stock",
                    label="U.S. Stock",
                    currentValue=1000.0,
                    actualPercent=50.0,
                    targetPercent=50.0,
                    rebalanceAmount=0.0,
                    deviationPercent=0.0,
                    action="BALANCED",
                )
            ],
            currencyExposure=CurrencyExposure(usd=1000.0, thb=1000.0, usdPercent=50.0, thbPercent=50.0),
            holdingsConcentration=[],
        )

    monkeypatch.setattr(AllocationService, "calculate_allocation", mock_calculate_allocation)

    res = api_client.post(
        "/portfolio/allocation?currency=USD",
        json={"targetAllocation": {"us-stock": 50.0, "thai-stock": 50.0}},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["totalPortfolioValue"] == 2000.0
    assert len(data["recommendations"]) == 1
    assert data["recommendations"][0]["action"] == "BALANCED"
