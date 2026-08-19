import pytest

from models.tools import (
    SimulateOrderResponse,
    SimulationDeltaMetrics,
    SimulationStateMetrics,
    SolveTargetCostResponse,
)
from services.tools_service import ToolsService


@pytest.mark.unit
def test_tools_router_simulate_endpoint(api_client, monkeypatch):
    async def mock_simulate(self, req):
        return SimulateOrderResponse(
            initial=SimulationStateMetrics(
                totalShares=100.0,
                averageCost=150.0,
                totalCost=15000.0,
                marketPrice=140.0,
                holdingValue=14000.0,
                unrealizedPL=-1000.0,
                unrealizedPLPercent=-6.67,
                realizedPL=0.0,
            ),
            simulated=SimulationStateMetrics(
                totalShares=200.0,
                averageCost=125.0,
                totalCost=25000.0,
                marketPrice=140.0,
                holdingValue=28000.0,
                unrealizedPL=3000.0,
                unrealizedPLPercent=12.0,
                realizedPL=0.0,
            ),
            delta=SimulationDeltaMetrics(
                shares=100.0,
                sharesPercent=100.0,
                averageCost=-25.0,
                averageCostPercent=-16.67,
                totalCost=10000.0,
                totalCostPercent=66.67,
                holdingValue=14000.0,
                holdingValuePercent=100.0,
                unrealizedPL=4000.0,
                unrealizedPLPercent=18.67,
                breakevenDistanceInitial=7.14,
                breakevenDistanceSimulated=-10.71,
                realizedPL=0.0,
            ),
            steps=req.steps,
            totalCapitalOutlay=10000.0,
            totalProceeds=0.0,
            totalFees=0.0,
            currency="USD",
        )

    monkeypatch.setattr(ToolsService, "simulate_order", mock_simulate)

    payload = {
        "initialPosition": {
            "symbol": "NVDA",
            "shares": 100.0,
            "avgCost": 150.0,
            "marketPrice": 140.0,
            "currency": "USD",
        },
        "steps": [{"action": "BUY", "shares": 100.0, "price": 100.0, "feePercent": 0.0}],
        "currency": "USD",
    }

    res = api_client.post("/portfolio/tools/simulate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["initial"]["totalShares"] == 100.0
    assert data["simulated"]["averageCost"] == 125.0
    assert data["delta"]["averageCost"] == -25.0


@pytest.mark.unit
def test_tools_router_solve_target_endpoint(api_client, monkeypatch):
    async def mock_solve(self, req):
        return SolveTargetCostResponse(
            isValid=True,
            requiredShares=100.0,
            requiredCapital=10000.0,
            feeAmount=0.0,
            totalOutlay=10000.0,
            achievedAvgCost=125.0,
            newTotalShares=200.0,
            newTotalCost=25000.0,
            currency="USD",
        )

    monkeypatch.setattr(ToolsService, "solve_target_cost", mock_solve)

    payload = {
        "initialPosition": {
            "symbol": "NVDA",
            "shares": 100.0,
            "avgCost": 150.0,
            "marketPrice": 140.0,
            "currency": "USD",
        },
        "targetAvgCost": 125.0,
        "purchasePrice": 100.0,
        "feePercent": 0.0,
    }

    res = api_client.post("/portfolio/tools/solve-target", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["isValid"] is True
    assert data["requiredShares"] == 100.0
    assert data["achievedAvgCost"] == 125.0


@pytest.mark.unit
def test_tools_router_tvm_endpoint(api_client, monkeypatch):
    from models.tools import TvmCalculateResponse

    async def mock_tvm(self, req):
        return TvmCalculateResponse(
            mode="FV",
            futureValue=73571.18,
            presentValue=10000.0,
            payment=500.0,
            annualRatePct=8.0,
            years=10.0,
            compounding="monthly",
            compoundingPeriodsPerYear=12,
            totalPeriods=120,
            totalPrincipal=10000.0,
            totalContributions=60000.0,
            totalInvested=70000.0,
            totalInterestEarned=3571.18,
            effectiveAnnualRatePct=8.30,
            multiplier=1.05,
            currency="USD",
            schedule=[],
            isValid=True,
        )

    monkeypatch.setattr(ToolsService, "calculate_tvm", mock_tvm)

    payload = {
        "mode": "FV",
        "presentValue": 10000.0,
        "payment": 500.0,
        "annualRatePct": 8.0,
        "years": 10.0,
        "compounding": "monthly",
        "timing": "end",
        "currency": "USD",
    }

    res = api_client.post("/portfolio/tools/tvm", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["isValid"] is True
    assert data["futureValue"] == 73571.18
    assert data["totalPrincipal"] == 10000.0
    assert data["compoundingPeriodsPerYear"] == 12


@pytest.mark.unit
def test_tools_router_rebalance_endpoint(api_client, monkeypatch):
    from models.tools import AssetClassRebalanceGroupModel, RebalanceCalculateResponse

    async def mock_rebalance(self, req):
        return RebalanceCalculateResponse(
            mode="standard",
            totalCurrentPortfolioValue=40000.0,
            totalTargetPortfolioValue=40000.0,
            cashContribution=0.0,
            totalBuyAmount=5000.0,
            totalSellAmount=5000.0,
            netCashDifference=0.0,
            groups=[
                AssetClassRebalanceGroupModel(
                    assetType="us-stock",
                    label="U.S. Stock",
                    color="#0ea5e9",
                    currentValue=40000.0,
                    targetValue=40000.0,
                    currentPortfolioPercent=100.0,
                    targetTotalPercent=100.0,
                    minInflowRequired=0.0,
                    totalBuyAmount=5000.0,
                    totalSellAmount=5000.0,
                    isValid=True,
                    symbols=[],
                )
            ],
            orders=[],
            currency="USD",
            isValid=True,
        )

    monkeypatch.setattr(ToolsService, "calculate_rebalance", mock_rebalance)

    payload = {
        "mode": "standard",
        "targetAllocations": {"NVDA": 50.0, "AAPL": 50.0},
        "currency": "USD",
    }

    res = api_client.post("/portfolio/tools/rebalance", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["isValid"] is True
    assert data["totalBuyAmount"] == 5000.0
    assert data["totalSellAmount"] == 5000.0
    assert len(data["groups"]) == 1
