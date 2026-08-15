import pytest

from models.portfolio import (
    ClosedPortfolioPosition,
    PortfolioHoldingsResponse,
    PortfolioPosition,
    PortfolioSummary,
)
from models.transaction import ClosedShareLot
from services.performance_service import PerformanceService


@pytest.fixture
def mock_holdings_response():
    open_pos = PortfolioPosition(
        symbol="AAPL",
        displaySymbol="AAPL",
        name="Apple Inc.",
        assetType="us-stock",
        assetTypeLabel="U.S. Stock",
        totalShares=10.0,
        totalCost=1000.0,
        averageCost=100.0,
        currentPrice=150.0,
        holdingValue=1500.0,
        unrealizedPL=500.0,
        unrealizedPLPercent=50.0,
        currency="USD",
        originalCurrency="USD",
        hasPrice=True,
        lots=[],
    )
    closed_lot_1 = ClosedShareLot(
        symbol="TSLA",
        purchaseDate="2023-01-01",
        closeDate="2023-05-01",
        quantity=5.0,
        costBasis=100.0,
        sellPrice=200.0,
        totalCost=500.0,
        totalProceeds=1000.0,
        realizedPL=500.0,
        realizedPLPercent=100.0,
        currency="USD",
        assetType="us-stock",
    )
    closed_lot_2 = ClosedShareLot(
        symbol="TSLA",
        purchaseDate="2023-01-01",
        closeDate="2024-02-01",
        quantity=5.0,
        costBasis=100.0,
        sellPrice=80.0,
        totalCost=500.0,
        totalProceeds=400.0,
        realizedPL=-100.0,
        realizedPLPercent=-20.0,
        currency="USD",
        assetType="us-stock",
    )
    closed_pos = ClosedPortfolioPosition(
        symbol="TSLA",
        displaySymbol="TSLA",
        name="Tesla Inc.",
        assetType="us-stock",
        assetTypeLabel="U.S. Stock",
        totalShares=0.0,
        closedShares=10.0,
        totalCost=1000.0,
        totalProceeds=1400.0,
        realizedPL=400.0,
        realizedPLPercent=40.0,
        averageBuyPrice=100.0,
        averageSellPrice=140.0,
        currency="USD",
        originalCurrency="USD",
        lots=[closed_lot_1, closed_lot_2],
    )
    summary = PortfolioSummary(
        totalInvested=2000.0,
        totalValue=1500.0,
        openInvested=1000.0,
        closedInvested=1000.0,
        totalUnrealizedPL=500.0,
        totalUnrealizedPLPercent=50.0,
        totalRealizedPL=400.0,
        totalRealizedPLPercent=40.0,
        totalReturn=900.0,
        totalReturnPercent=45.0,
    )
    return PortfolioHoldingsResponse(
        currency="USD",
        exchangeRate=1.0,
        tabId="all",
        summary=summary,
        openPositions=[open_pos],
        closedPositions=[closed_pos],
    )


@pytest.mark.unit
def test_calculate_performance_all_timeframe(mock_holdings_response):
    service = PerformanceService()
    res = service.calculate_performance(
        holdings_res=mock_holdings_response,
        timeframe="ALL",
    )

    assert res.timeframe == "ALL"
    assert len(res.assetTypePerformance) == 1
    at = res.assetTypePerformance[0]
    assert at.assetType == "us-stock"
    assert at.investedCost == 2000.0
    assert at.unrealizedPL == 500.0
    assert at.realizedPL == 400.0
    assert at.totalReturn == 900.0
    assert at.totalReturnPercent == 45.0
    assert at.openSymbolCount == 1
    assert at.closedSymbolCount == 1

    assert len(res.symbolPerformance) == 2
    assert len(res.topGainers) == 2
    assert len(res.topLosers) == 0


@pytest.mark.unit
def test_calculate_performance_date_filtering(mock_holdings_response):
    service = PerformanceService()
    # Filter only year 2024 (should include closed_lot_2 only: realizedPL = -100, cost = 500)
    res = service.calculate_performance(
        holdings_res=mock_holdings_response,
        timeframe="CUSTOM",
        start_date="2024-01-01",
        end_date="2024-12-31",
    )

    assert res.summary.closedInvested == 500.0
    assert res.summary.totalRealizedPL == -100.0
    assert res.summary.totalInvested == 1500.0  # 1000 open + 500 closed
    assert res.summary.totalReturn == 400.0  # 500 unrealized - 100 realized

    # Check top losers
    assert len(res.topLosers) == 1
    assert res.topLosers[0].symbol == "TSLA"
