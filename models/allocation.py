from pydantic import BaseModel


class RebalanceRecommendation(BaseModel):
    assetType: str
    label: str
    currentValue: float
    actualPercent: float
    targetPercent: float
    rebalanceAmount: float
    deviationPercent: float
    action: str  # 'BUY' | 'SELL' | 'BALANCED'


class CurrencyExposure(BaseModel):
    usd: float
    thb: float
    usdPercent: float
    thbPercent: float


class HoldingConcentration(BaseModel):
    symbol: str
    displaySymbol: str
    name: str = ""
    assetType: str
    value: float
    portfolioPercent: float
    classPercent: float


class TargetAllocationRequest(BaseModel):
    targetAllocation: dict[str, float] = {
        'us-stock': 40.0,
        'thai-stock': 30.0,
        'crypto': 15.0,
        'mutual-fund': 15.0,
    }


class PortfolioAllocationResponse(BaseModel):
    currency: str
    exchangeRate: float
    totalPortfolioValue: float
    recommendations: list[RebalanceRecommendation] = []
    currencyExposure: CurrencyExposure
    holdingsConcentration: list[HoldingConcentration] = []
    error: str | None = None
