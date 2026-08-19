from fastapi import APIRouter, Depends

from models.tools import (
    RebalanceCalculateRequest,
    RebalanceCalculateResponse,
    SimulateOrderRequest,
    SimulateOrderResponse,
    SolveTargetCostRequest,
    SolveTargetCostResponse,
    TvmCalculateRequest,
    TvmCalculateResponse,
)
from services.tools_service import ToolsService
from services.valuation_service import ValuationService
from utils.auth import verify_api_key

router = APIRouter(
    prefix="/portfolio/tools",
    tags=["tools"],
    dependencies=[Depends(verify_api_key)],
)

valuation_service = ValuationService()
tools_service = ToolsService(valuation_service=valuation_service)


@router.post("/simulate", response_model=SimulateOrderResponse)
async def simulate_orders(req: SimulateOrderRequest) -> SimulateOrderResponse:
    """
    Simulates forward Buy and Sell orders to project changes in average cost basis,
    total invested capital, market value, unrealized/realized P/L, and breakeven distance.
    """
    return await tools_service.simulate_order(req)


@router.post("/solve-target", response_model=SolveTargetCostResponse)
async def solve_target_cost(req: SolveTargetCostRequest) -> SolveTargetCostResponse:
    """
    Calculates exact required share quantity and capital outlay to reach a target average cost basis.
    Validates mathematical boundaries and feasibility.
    """
    return await tools_service.solve_target_cost(req)


@router.post("/tvm", response_model=TvmCalculateResponse)
async def calculate_tvm(req: TvmCalculateRequest) -> TvmCalculateResponse:
    """
    Calculates Time Value of Money (TVM) parameters including Future Value,
    required periodic contributions, starting capital, investment horizon, and return rate (CAGR).
    """
    return await tools_service.calculate_tvm(req)


@router.post("/rebalance", response_model=RebalanceCalculateResponse)
async def calculate_rebalance(req: RebalanceCalculateRequest) -> RebalanceCalculateResponse:
    """
    Calculates portfolio rebalance actions across asset classes for standard (buy/sell)
    and no-sell (minimum inflow & custom contribution) modes.
    """
    return await tools_service.calculate_rebalance(req)


