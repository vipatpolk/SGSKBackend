from pydantic import BaseModel

from models.portfolio import PortfolioSummary


class AssetClassPerformance(BaseModel):
    assetType: str
    label: str
    investedCost: float
    currentValue: float
    unrealizedPL: float
    realizedPL: float
    totalReturn: float
    totalReturnPercent: float
    openSymbolCount: int
    closedSymbolCount: int


class SymbolPerformance(BaseModel):
    symbol: str
    displaySymbol: str
    name: str = ""
    assetType: str
    assetTypeLabel: str
    status: str  # 'OPEN' | 'CLOSED' | 'BOTH'
    investedCost: float
    currentValue: float
    unrealizedPL: float
    realizedPL: float
    totalReturnAmount: float
    totalReturn: float
    totalReturnPercent: float
    hasPrice: bool


class PortfolioPerformanceResponse(BaseModel):
    timeframe: str
    startDate: str = ""
    endDate: str = ""
    currency: str
    exchangeRate: float
    summary: PortfolioSummary
    assetTypePerformance: list[AssetClassPerformance] = []
    topGainers: list[SymbolPerformance] = []
    topLosers: list[SymbolPerformance] = []
    symbolPerformance: list[SymbolPerformance] = []
    error: str | None = None
