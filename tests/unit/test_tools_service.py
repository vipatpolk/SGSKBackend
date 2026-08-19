import pytest

from models.tools import (
    PositionSnapshotModel,
    SimulatedStepModel,
    SimulateOrderRequest,
    SolveTargetCostRequest,
)
from services.tools_service import ToolsService


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tools_service_simulate_buy_averaging_down():
    service = ToolsService()
    initial = PositionSnapshotModel(
        symbol="NVDA",
        shares=100.0,
        avgCost=150.0,
        marketPrice=120.0,
        currency="USD",
        totalCost=15000.0,
    )
    req = SimulateOrderRequest(
        initialPosition=initial,
        steps=[
            SimulatedStepModel(action="BUY", shares=100.0, price=100.0, feePercent=0.0),
        ],
    )
    res = await service.simulate_order(req)

    assert res.initial.totalShares == 100.0
    assert res.initial.averageCost == 150.0
    assert res.initial.totalCost == 15000.0

    assert res.simulated.totalShares == 200.0
    assert res.simulated.averageCost == 125.0
    assert res.simulated.totalCost == 25000.0
    assert res.simulated.holdingValue == 24000.0
    assert res.simulated.unrealizedPL == -1000.0
    assert res.simulated.unrealizedPLPercent == -4.0

    assert res.delta.shares == 100.0
    assert res.delta.averageCost == -25.0
    assert res.delta.averageCostPercent == round((-25.0 / 150.0) * 100.0, 2)
    assert res.totalCapitalOutlay == 10000.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tools_service_simulate_buy_with_fee():
    service = ToolsService()
    initial = PositionSnapshotModel(
        symbol="PTT.BK",
        shares=1000.0,
        avgCost=35.0,
        marketPrice=32.0,
        currency="THB",
        totalCost=35000.0,
    )
    # Buy 1000 shares @ 30 THB with 0.157% commission
    req = SimulateOrderRequest(
        initialPosition=initial,
        steps=[
            SimulatedStepModel(action="BUY", shares=1000.0, price=30.0, feePercent=0.157),
        ],
    )
    res = await service.simulate_order(req)

    expected_fee = 1000.0 * 30.0 * (0.157 / 100.0)  # 47.1 THB
    expected_outlay = 30000.0 + expected_fee

    assert res.totalFees == round(expected_fee, 2)
    assert res.simulated.totalShares == 2000.0
    assert res.simulated.totalCost == round(35000.0 + expected_outlay, 2)
    assert res.simulated.averageCost == round((35000.0 + expected_outlay) / 2000.0, 4)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tools_service_simulate_sell_realized_pl():
    service = ToolsService()
    initial = PositionSnapshotModel(
        symbol="AAPL",
        shares=100.0,
        avgCost=150.0,
        marketPrice=180.0,
        currency="USD",
        totalCost=15000.0,
    )
    # Sell 50 shares @ 180 USD (cost basis = 50 * 150 = 7500, proceeds = 9000 -> Realized P/L = +1500)
    req = SimulateOrderRequest(
        initialPosition=initial,
        steps=[
            SimulatedStepModel(action="SELL", shares=50.0, price=180.0, feePercent=0.0),
        ],
    )
    res = await service.simulate_order(req)

    assert res.simulated.totalShares == 50.0
    assert res.simulated.averageCost == 150.0
    assert res.simulated.totalCost == 7500.0
    assert res.simulated.realizedPL == 1500.0
    assert res.totalProceeds == 9000.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tools_service_solve_target_cost_feasible():
    service = ToolsService()
    initial = PositionSnapshotModel(
        symbol="NVDA",
        shares=100.0,
        avgCost=150.0,
        marketPrice=120.0,
        currency="USD",
        totalCost=15000.0,
    )
    # Target avg cost = 125, Buy price = 100 -> Expected: 100 shares ($10,000)
    req = SolveTargetCostRequest(
        initialPosition=initial,
        targetAvgCost=125.0,
        purchasePrice=100.0,
        feePercent=0.0,
    )
    res = await service.solve_target_cost(req)

    assert res.isValid is True
    assert res.requiredShares == 100.0
    assert res.requiredCapital == 10000.0
    assert res.newTotalShares == 200.0
    assert res.achievedAvgCost == 125.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tools_service_solve_target_cost_infeasible():
    service = ToolsService()
    initial = PositionSnapshotModel(
        symbol="NVDA",
        shares=100.0,
        avgCost=150.0,
        marketPrice=120.0,
        currency="USD",
        totalCost=15000.0,
    )
    # Trying to average down to 125 with buy price of 130 (impossible)
    req = SolveTargetCostRequest(
        initialPosition=initial,
        targetAvgCost=125.0,
        purchasePrice=130.0,
        feePercent=0.0,
    )
    res = await service.solve_target_cost(req)

    assert res.isValid is False
    assert "Cannot average down" in res.errorMessage


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tools_service_solve_target_cost_averaging_up():
    service = ToolsService()
    initial = PositionSnapshotModel(
        symbol="MSFT",
        shares=100.0,
        avgCost=300.0,
        marketPrice=350.0,
        currency="USD",
        totalCost=30000.0,
    )
    # Target avg cost = 320, Buy price = 340 -> (30,000 - 100*320) / (320 - 340) = -2000 / -20 = 100 shares
    req = SolveTargetCostRequest(
        initialPosition=initial,
        targetAvgCost=320.0,
        purchasePrice=340.0,
        feePercent=0.0,
    )
    res = await service.solve_target_cost(req)

    assert res.isValid is True
    assert res.requiredShares == 100.0
    assert res.requiredCapital == 34000.0
    assert res.newTotalShares == 200.0
    assert res.achievedAvgCost == 320.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tools_service_multi_step_buy_and_sell_chain():
    service = ToolsService()
    initial = PositionSnapshotModel(
        symbol="NVDA",
        shares=100.0,
        avgCost=150.0,
        marketPrice=160.0,
        currency="USD",
        totalCost=15000.0,
    )
    # Step 1: Buy 100 shares @ 100 -> Total 200 shares, avg cost 125, total cost 25,000
    # Step 2: Sell 50 shares @ 160 -> Cost basis sold = 50 * 125 = 6250, proceeds = 8000, realized PL = +1750
    # Final: 150 shares, avg cost 125, total cost 18,750
    req = SimulateOrderRequest(
        initialPosition=initial,
        steps=[
            SimulatedStepModel(action="BUY", shares=100.0, price=100.0, feePercent=0.0),
            SimulatedStepModel(action="SELL", shares=50.0, price=160.0, feePercent=0.0),
        ],
    )
    res = await service.simulate_order(req)

    assert res.simulated.totalShares == 150.0
    assert res.simulated.averageCost == 125.0
    assert res.simulated.totalCost == 18750.0
    assert res.simulated.realizedPL == 1750.0
    assert res.totalCapitalOutlay == 10000.0
    assert res.totalProceeds == 8000.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tools_service_solve_target_cost_zero_initial_shares():
    service = ToolsService()
    initial = PositionSnapshotModel(
        symbol="NEW",
        shares=0.0,
        avgCost=0.0,
        marketPrice=50.0,
        currency="USD",
        totalCost=0.0,
    )
    req = SolveTargetCostRequest(
        initialPosition=initial,
        targetAvgCost=50.0,
        purchasePrice=50.0,
        feePercent=0.0,
    )
    res = await service.solve_target_cost(req)

    assert res.isValid is True
    assert res.requiredShares == 1.0
    assert res.requiredCapital == 50.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tools_service_calculate_tvm_fv_mode():
    service = ToolsService()
    from models.tools import TvmCalculateRequest

    # $10,000 PV, $500/mo, 8% annual rate, 10 years, monthly compounding
    req = TvmCalculateRequest(
        mode="FV",
        presentValue=10000.0,
        payment=500.0,
        annualRatePct=8.0,
        years=10.0,
        compounding="monthly",
        timing="end",
    )
    res = await service.calculate_tvm(req)

    assert res.isValid is True
    assert res.futureValue > res.totalInvested
    assert res.totalPrincipal == 10000.0
    assert res.totalContributions == 500.0 * 120
    assert res.totalInvested == 70000.0
    assert res.effectiveAnnualRatePct == 8.30
    assert len(res.schedule) == 10


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tools_service_calculate_tvm_solve_payment():
    service = ToolsService()
    from models.tools import TvmCalculateRequest

    req = TvmCalculateRequest(
        mode="PMT",
        presentValue=50000.0,
        targetFutureValue=1000000.0,
        annualRatePct=7.0,
        years=20.0,
        compounding="monthly",
        timing="end",
    )
    res = await service.calculate_tvm(req)

    assert res.isValid is True
    assert res.payment > 0.0

    # Re-evaluating with this payment should yield approx 1,000,000
    check_req = TvmCalculateRequest(
        mode="FV",
        presentValue=50000.0,
        payment=res.payment,
        annualRatePct=7.0,
        years=20.0,
        compounding="monthly",
        timing="end",
    )
    check_res = await service.calculate_tvm(check_req)
    assert abs(check_res.futureValue - 1000000.0) < 100.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tools_service_calculate_tvm_solve_years_and_rate():
    service = ToolsService()
    from models.tools import TvmCalculateRequest

    # Solve for N (years)
    req_n = TvmCalculateRequest(
        mode="N",
        presentValue=20000.0,
        payment=1000.0,
        targetFutureValue=500000.0,
        annualRatePct=8.0,
        compounding="monthly",
    )
    res_n = await service.calculate_tvm(req_n)
    assert res_n.isValid is True
    assert res_n.years > 0.0

    # Solve for RATE
    req_rate = TvmCalculateRequest(
        mode="RATE",
        presentValue=100000.0,
        payment=2000.0,
        targetFutureValue=1000000.0,
        years=15.0,
        compounding="monthly",
    )
    res_rate = await service.calculate_tvm(req_rate)
    assert res_rate.isValid is True
    assert res_rate.annualRatePct > 0.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tools_service_calculate_tvm_all_compounding_frequencies():
    service = ToolsService()
    from models.tools import CompoundingFrequency, TvmCalculateRequest

    frequencies: list[CompoundingFrequency] = [
        "daily",
        "weekly",
        "biweekly",
        "semimonthly",
        "monthly",
        "quarterly",
        "semiannually",
        "annually",
    ]

    for freq in frequencies:
        req = TvmCalculateRequest(
            mode="FV",
            presentValue=10000.0,
            payment=100.0,
            annualRatePct=6.0,
            years=5.0,
            compounding=freq,
        )
        res = await service.calculate_tvm(req)
        assert res.isValid is True
        assert res.futureValue > 10000.0
        assert res.compounding == freq


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tools_service_calculate_tvm_solve_pv():
    service = ToolsService()
    from models.tools import TvmCalculateRequest

    req = TvmCalculateRequest(
        mode="PV",
        targetFutureValue=500000.0,
        payment=1000.0,
        annualRatePct=8.0,
        years=10.0,
        compounding="monthly",
    )
    res = await service.calculate_tvm(req)
    assert res.isValid is True
    assert res.presentValue > 0.0
    assert res.futureValue == 500000.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tools_service_calculate_rebalance_standard_and_no_sell(monkeypatch):
    service = ToolsService()
    from unittest.mock import AsyncMock

    from models.portfolio import PortfolioHoldingsResponse, PortfolioPosition, PortfolioSummary
    from models.tools import RebalanceCalculateRequest

    mock_positions = [
        PortfolioPosition(
            symbol="NVDA",
            displaySymbol="NVDA",
            name="NVIDIA Corp",
            assetType="us-stock",
            assetTypeLabel="US Stock",
            currency="USD",
            originalCurrency="USD",
            totalShares=100.0,
            averageCost=100.0,
            totalCost=10000.0,
            currentPrice=150.0,
            holdingValue=15000.0,
            unrealizedPL=5000.0,
            unrealizedPLPercent=50.0,
            hasPrice=True,
            lots=[],
        ),
        PortfolioPosition(
            symbol="AAPL",
            displaySymbol="AAPL",
            name="Apple Inc",
            assetType="us-stock",
            assetTypeLabel="US Stock",
            currency="USD",
            originalCurrency="USD",
            totalShares=100.0,
            averageCost=200.0,
            totalCost=20000.0,
            currentPrice=250.0,
            holdingValue=25000.0,
            unrealizedPL=5000.0,
            unrealizedPLPercent=25.0,
            hasPrice=True,
            lots=[],
        ),
    ]

    mock_holdings = PortfolioHoldingsResponse(
        currency="USD",
        exchangeRate=1.0,
        tabId="all",
        summary=PortfolioSummary(
            totalInvested=30000.0,
            totalValue=40000.0,
            openInvested=30000.0,
            closedInvested=0.0,
            totalUnrealizedPL=10000.0,
            totalUnrealizedPLPercent=33.33,
            totalRealizedPL=0.0,
            totalRealizedPLPercent=0.0,
            totalReturn=10000.0,
            totalReturnPercent=33.33,
        ),
        openPositions=mock_positions,
        closedPositions=[],
        error=None,
    )

    monkeypatch.setattr(service.valuation_service, "get_portfolio_holdings", AsyncMock(return_value=mock_holdings))

    # Standard mode: 50% NVDA, 50% AAPL (each 20,000)
    req_std = RebalanceCalculateRequest(
        mode="standard",
        targetAllocations={"NVDA": 50.0, "AAPL": 50.0},
        currency="USD",
    )
    res_std = await service.calculate_rebalance(req_std)
    assert res_std.isValid is True
    assert res_std.totalBuyAmount == 5000.0
    assert res_std.totalSellAmount == 5000.0
    assert len(res_std.orders) == 2

    # No-Sell mode: 50% NVDA, 50% AAPL -> AAPL is anchor (25k), NVDA needs 10k buy
    req_no_sell = RebalanceCalculateRequest(
        mode="no-sell",
        noSellSubMode="min-inflow",
        targetAllocations={"NVDA": 50.0, "AAPL": 50.0},
        currency="USD",
    )
    res_no_sell = await service.calculate_rebalance(req_no_sell)
    assert res_no_sell.isValid is True
    assert res_no_sell.cashContribution == 10000.0
    assert res_no_sell.totalBuyAmount == 10000.0
    assert res_no_sell.totalSellAmount == 0.0



