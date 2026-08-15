from fastapi import APIRouter, Depends, Query

from models.allocation import PortfolioAllocationResponse, TargetAllocationRequest
from models.dividend import PortfolioDividendResponse
from models.performance import PortfolioPerformanceResponse
from models.portfolio import PortfolioHoldingsResponse
from services.allocation_service import AllocationService
from services.dividend_service import DividendService
from services.performance_service import PerformanceService
from services.valuation_service import ValuationService
from utils.auth import verify_api_key

router = APIRouter(prefix="/portfolio", tags=["portfolio"], dependencies=[Depends(verify_api_key)])

valuation_service = ValuationService()
performance_service = PerformanceService(valuation_service=valuation_service)
allocation_service = AllocationService(valuation_service=valuation_service)
dividend_service = DividendService(valuation_service=valuation_service)


@router.get("/holdings", response_model=PortfolioHoldingsResponse)
async def get_portfolio_holdings(
    tab_id: str = Query("all", description="Asset tab ID (all, us-stock, thai-stock, crypto, mutual-fund, closed-position)"),
    currency: str = Query("THB", description="Display currency (THB or USD)"),
):
    return await valuation_service.get_portfolio_holdings(tab_id=tab_id, currency=currency)


@router.get("/performance", response_model=PortfolioPerformanceResponse)
async def get_portfolio_performance(
    timeframe: str = Query("ALL", description="Timeframe preset (YTD, 1M, 3M, 6M, 1Y, ALL, CUSTOM)"),
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD) for custom timeframe"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD) for custom timeframe"),
    currency: str = Query("THB", description="Display currency (THB or USD)"),
):
    return await performance_service.get_performance_analytics(
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        currency=currency,
    )


@router.post("/allocation", response_model=PortfolioAllocationResponse)
async def get_portfolio_allocation(
    req: TargetAllocationRequest | None = None,
    currency: str = Query("THB", description="Display currency (THB or USD)"),
):
    targets = req.targetAllocation if req else None
    return await allocation_service.calculate_allocation(targets=targets, currency=currency)


@router.get("/dividend", response_model=PortfolioDividendResponse)
async def get_portfolio_dividend(
    currency: str = Query("THB", description="Display currency (THB or USD)"),
    tab_id: str = Query("all", description="Asset tab ID"),
):
    return await dividend_service.get_dividend_analytics(currency=currency, tab_id=tab_id)
