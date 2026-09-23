import pytest

from models.portfolio import PortfolioHoldingsResponse
from models.transaction import ClosedShareLot, ClosedSymbolSummary, PriceData, ShareLot, SheetResult, SymbolSummary
from services.valuation_service import ValuationService


@pytest.fixture
def mock_sheet_result():
    open_lot = ShareLot(
        symbol="AAPL",
        purchaseDate="2023-01-01",
        quantity=10.0,
        costBasis=150.0,
        totalCost=1500.0,
        assetType="us-stock",
    )
    open_summary = SymbolSummary(
        symbol="AAPL",
        totalShares=10.0,
        totalCost=1500.0,
        averageCost=150.0,
        currency="USD",
        lots=[open_lot],
        assetType="us-stock",
    )
    closed_lot = ClosedShareLot(
        symbol="TSLA",
        purchaseDate="2023-01-01",
        closeDate="2023-06-01",
        quantity=5.0,
        costBasis=200.0,
        sellPrice=300.0,
        totalCost=1000.0,
        totalProceeds=1500.0,
        realizedPL=500.0,
        realizedPLPercent=50.0,
        currency="USD",
        assetType="us-stock",
    )
    closed_summary = ClosedSymbolSummary(
        symbol="TSLA",
        totalShares=0.0,
        closedShares=5.0,
        totalCost=1000.0,
        totalProceeds=1500.0,
        realizedPL=500.0,
        realizedPLPercent=50.0,
        averageBuyPrice=200.0,
        averageSellPrice=300.0,
        currency="USD",
        lots=[closed_lot],
        assetType="us-stock",
    )
    return SheetResult(
        summaries=[open_summary],
        closedSummaries=[closed_summary],
        transactionSummaries=[],
        rawTransactions=[],
        totalCostByCurrency={"USD": 2500.0},
        totalProceedsByCurrency={"USD": 1500.0},
        totalRealizedPLByCurrency={"USD": 500.0},
        totalSymbols=2,
        totalLots=1,
    )


@pytest.mark.unit
def test_value_sheet_result_usd(mock_sheet_result):
    service = ValuationService()
    price_map = {
        "AAPL": PriceData(symbol="AAPL", name="Apple Inc.", price=180.0, currency="USD"),
        "TSLA": PriceData(symbol="TSLA", name="Tesla Inc.", price=250.0, currency="USD"),
    }

    res: PortfolioHoldingsResponse = service.value_sheet_result(
        sheet_result=mock_sheet_result,
        price_data_map=price_map,
        exchange_rate=35.0,
        target_currency="USD",
    )

    assert res.currency == "USD"
    assert len(res.openPositions) == 1
    pos = res.openPositions[0]
    assert pos.symbol == "AAPL"
    assert pos.currentPrice == 180.0
    assert pos.holdingValue == 1800.0
    assert pos.unrealizedPL == 300.0
    assert pos.unrealizedPLPercent == 20.0
    assert len(pos.lots) == 1
    assert pos.lots[0].holdingValue == 1800.0

    assert len(res.closedPositions) == 1
    closed = res.closedPositions[0]
    assert closed.symbol == "TSLA"
    assert closed.realizedPL == 500.0
    assert closed.realizedPLPercent == 50.0

    # Summary
    assert res.summary.openInvested == 1500.0
    assert res.summary.closedInvested == 1000.0
    assert res.summary.totalInvested == 2500.0
    assert res.summary.totalValue == 1800.0
    assert res.summary.totalUnrealizedPL == 300.0
    assert res.summary.totalRealizedPL == 500.0
    assert res.summary.totalReturn == 800.0


@pytest.mark.unit
def test_value_sheet_result_thb(mock_sheet_result):
    service = ValuationService()
    price_map = {
        "AAPL": PriceData(symbol="AAPL", name="Apple Inc.", price=180.0, currency="USD"),
    }

    res: PortfolioHoldingsResponse = service.value_sheet_result(
        sheet_result=mock_sheet_result,
        price_data_map=price_map,
        exchange_rate=35.0,
        target_currency="THB",
    )

    assert res.currency == "THB"
    pos = res.openPositions[0]
    assert pos.totalCost == 1500.0 * 35.0
    assert pos.holdingValue == 1800.0 * 35.0
    assert pos.unrealizedPL == 300.0 * 35.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_portfolio_holdings_error_handling(monkeypatch):
    service = ValuationService()

    async def mock_fetch(tab_id):
        return SheetResult(
            summaries=[],
            closedSummaries=[],
            totalCostByCurrency={},
            totalProceedsByCurrency={},
            totalRealizedPLByCurrency={},
            totalSymbols=0,
            totalLots=0,
            error="Sheet load failed",
        )

    monkeypatch.setattr(service.share_lot_service, "fetch_sheet", mock_fetch)

    res = await service.get_portfolio_holdings("us-stock", "THB")
    assert res.error == "Sheet load failed"
    assert len(res.openPositions) == 0


@pytest.mark.unit
def test_value_provident_fund_positions():
    """Verify valuing Provident Fund positions with implied NAV, SEC fund name, and employee/employer shares."""
    service = ValuationService()

    pvd_lot_emp = ShareLot(
        symbol="PVDSP500",
        purchaseDate="2026-09-01",
        quantity=8294.68,
        costBasis=14.3452,
        totalCost=118988.82,
        assetType="provident-fund",
        note="Employee Contribution",
    )
    pvd_lot_empr = ShareLot(
        symbol="PVDSP500",
        purchaseDate="2026-09-01",
        quantity=6005.29,
        costBasis=14.3452,
        totalCost=86147.07,
        assetType="provident-fund",
        note="Employer Matching",
    )
    pvd_summary = SymbolSummary(
        symbol="PVDSP500",
        totalShares=14299.97,
        totalCost=205135.89,
        averageCost=14.3452,
        currency="THB",
        lots=[pvd_lot_emp, pvd_lot_empr],
        assetType="provident-fund",
        employeeShares=8294.68,
        employerShares=6005.29,
    )

    sheet_result = SheetResult(
        summaries=[pvd_summary],
        closedSummaries=[],
        transactionSummaries=[],
        rawTransactions=[],
        totalCostByCurrency={"THB": 205135.89},
        totalProceedsByCurrency={},
        totalRealizedPLByCurrency={},
        totalSymbols=1,
        totalLots=2,
    )

    price_map = {
        "PVDSP500": PriceData(
            symbol="PVDSP500",
            name="นโยบายกองทุนรวมต่างประเทศ หุ้นยูเอส",
            price=0.0,
            currency="THB",
        )
    }

    res = service.value_sheet_result(
        sheet_result=sheet_result,
        price_data_map=price_map,
        exchange_rate=35.0,
        target_currency="THB",
        tab_id="provident-fund",
    )

    assert len(res.openPositions) == 1
    pos = res.openPositions[0]
    assert pos.symbol == "PVDSP500"
    assert pos.name == "นโยบายกองทุนรวมต่างประเทศ หุ้นยูเอส"
    assert pos.assetType == "provident-fund"
    assert pos.assetTypeLabel == "Provident Fund"
    assert pos.hasPrice is True
    assert abs(pos.totalCost - 205135.89) < 0.1
    assert abs(pos.holdingValue - 205135.89) < 0.1
    assert pos.unrealizedPL == 0.0
    assert pos.employeeShares == 8294.68
    assert pos.employerShares == 6005.29
    assert len(pos.lots) == 2
    assert pos.lots[0].note == "Employee Contribution"
    assert pos.lots[1].note == "Employer Matching"


@pytest.mark.unit
def test_value_provident_fund_positions_with_earnings():
    """Verify valuing Provident Fund positions with contribution, earnings, implied NAV, and unrealized return."""
    service = ValuationService()

    pvd_lot_emp = ShareLot(
        symbol="PVDSP500",
        purchaseDate="2026-09-01",
        quantity=8294.68,
        costBasis=100858.26 / 8294.68,
        totalCost=100858.26,
        assetType="provident-fund",
        note="Employee Contribution",
    )
    pvd_lot_empr = ShareLot(
        symbol="PVDSP500",
        purchaseDate="2026-09-01",
        quantity=6005.29,
        costBasis=73962.72 / 6005.29,
        totalCost=73962.72,
        assetType="provident-fund",
        note="Employer Matching",
    )
    pvd_summary = SymbolSummary(
        symbol="PVDSP500",
        totalShares=14299.97,
        totalCost=100858.26 + 73962.72,
        averageCost=(100858.26 + 73962.72) / 14299.97,
        currency="THB",
        lots=[pvd_lot_emp, pvd_lot_empr],
        assetType="provident-fund",
        employeeShares=8294.68,
        employerShares=6005.29,
        employeeContribution=100858.26,
        employeeEarnings=18130.55,
        employerMatching=73962.72,
        employerEarnings=12184.36,
    )

    sheet_result = SheetResult(
        summaries=[pvd_summary],
        closedSummaries=[],
        transactionSummaries=[],
        rawTransactions=[],
        totalCostByCurrency={"THB": 174820.98},
        totalProceedsByCurrency={},
        totalRealizedPLByCurrency={},
        totalSymbols=1,
        totalLots=2,
    )

    price_map = {
        "PVDSP500": PriceData(
            symbol="PVDSP500",
            name="นโยบายกองทุนรวมต่างประเทศ หุ้นยูเอส",
            price=0.0,
            currency="THB",
        )
    }

    res = service.value_sheet_result(
        sheet_result=sheet_result,
        price_data_map=price_map,
        exchange_rate=35.0,
        target_currency="THB",
        tab_id="provident-fund",
    )

    assert len(res.openPositions) == 1
    pos = res.openPositions[0]
    assert pos.symbol == "PVDSP500"
    assert pos.employeeContribution == 100858.26
    assert pos.employeeEarnings == 18130.55
    assert pos.employerMatching == 73962.72
    assert pos.employerEarnings == 12184.36
    # Total Cost = 174,820.98
    assert abs(pos.totalCost - 174820.98) < 0.1
    # Holding Value = 205,135.89
    assert abs(pos.holdingValue - 205135.89) < 0.1
    # Unrealized PL = 30,314.91
    assert abs(pos.unrealizedPL - 30314.91) < 0.1
    # NAV price = 205,135.89 / 14,299.97 = 14.3452...
    assert abs(pos.currentPrice - (205135.89 / 14299.97)) < 1e-4

