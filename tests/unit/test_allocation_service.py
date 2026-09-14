import pytest

from models.portfolio import (
    PortfolioHoldingsResponse,
    PortfolioPosition,
    PortfolioSummary,
)
from services.allocation_service import AllocationService


@pytest.fixture
def mock_holdings_for_allocation():
    pos_us = PortfolioPosition(
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
    pos_thai = PortfolioPosition(
        symbol="PTT.BK",
        displaySymbol="PTT",
        name="PTT PCL",
        assetType="thai-stock",
        assetTypeLabel="Thai Stock",
        totalShares=100.0,
        totalCost=300.0,
        averageCost=3.0,
        currentPrice=5.0,
        holdingValue=500.0,
        unrealizedPL=200.0,
        unrealizedPLPercent=66.67,
        currency="USD",
        originalCurrency="THB",
        hasPrice=True,
        lots=[],
    )
    summary = PortfolioSummary(
        totalInvested=1300.0,
        totalValue=2000.0,
        openInvested=1300.0,
        closedInvested=0.0,
        totalUnrealizedPL=700.0,
        totalUnrealizedPLPercent=53.85,
        totalRealizedPL=0.0,
        totalRealizedPLPercent=0.0,
        totalReturn=700.0,
        totalReturnPercent=53.85,
    )
    return PortfolioHoldingsResponse(
        currency="USD",
        exchangeRate=1.0,
        tabId="all",
        summary=summary,
        openPositions=[pos_us, pos_thai],
        closedPositions=[],
    )


@pytest.mark.unit
def test_process_allocation(mock_holdings_for_allocation):
    service = AllocationService()
    # Target: 50% US Stock, 50% Thai Stock
    targets = {
        "us-stock": 50.0,
        "thai-stock": 50.0,
        "crypto": 0.0,
        "mutual-fund": 0.0,
    }

    res = service.process_allocation(
        holdings_res=mock_holdings_for_allocation,
        targets=targets,
    )

    assert res.totalPortfolioValue == 2000.0
    assert len(res.recommendations) >= 4

    us_rec = next(r for r in res.recommendations if r.assetType == "us-stock")
    assert us_rec.currentValue == 1500.0
    assert us_rec.actualPercent == 75.0
    assert us_rec.targetPercent == 50.0
    assert us_rec.rebalanceAmount == -500.0  # Sell 500
    assert us_rec.action == "SELL"

    thai_rec = next(r for r in res.recommendations if r.assetType == "thai-stock")
    assert thai_rec.currentValue == 500.0
    assert thai_rec.actualPercent == 25.0
    assert thai_rec.targetPercent == 50.0
    assert thai_rec.rebalanceAmount == 500.0  # Buy 500
    assert thai_rec.action == "BUY"

    bond_rec = next(r for r in res.recommendations if r.assetType == "bond")
    assert bond_rec.currentValue == 0.0
    assert bond_rec.action == "BALANCED"

    # Currency Exposure (AAPL is USD, PTT is THB)
    assert res.currencyExposure.usd == 1500.0
    assert res.currencyExposure.thb == 500.0
    assert res.currencyExposure.usdPercent == 75.0
    assert res.currencyExposure.thbPercent == 25.0

    # Concentration
    assert len(res.holdingsConcentration) == 2
    assert res.holdingsConcentration[0].symbol == "AAPL"
    assert res.holdingsConcentration[0].portfolioPercent == 75.0
