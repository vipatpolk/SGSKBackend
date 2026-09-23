from pydantic import BaseModel

from models.transaction import ClosedShareLot, SymbolTransactionSummary, Transaction


class PortfolioHoldingLot(BaseModel):
    purchaseDate: str
    quantity: float
    costBasis: float
    totalCost: float
    currentPrice: float
    holdingValue: float
    unrealizedPL: float
    unrealizedPLPercent: float
    assetType: str
    currency: str
    originalCostBasis: float
    originalCurrency: str
    note: str | None = None


class PortfolioPosition(BaseModel):
    symbol: str
    displaySymbol: str
    name: str = ""
    assetType: str
    assetTypeLabel: str
    totalShares: float
    totalCost: float
    averageCost: float
    currentPrice: float
    holdingValue: float
    unrealizedPL: float
    unrealizedPLPercent: float
    currency: str
    originalCurrency: str
    hasPrice: bool
    lots: list[PortfolioHoldingLot] = []
    employeeShares: float | None = None
    employerShares: float | None = None
    employeeContribution: float | None = None
    employeeEarnings: float | None = None
    employerMatching: float | None = None
    employerEarnings: float | None = None
    policyName: str | None = None
    aimcType: str | None = None
    riskLevel: str | None = None


class ClosedPortfolioPosition(BaseModel):
    symbol: str
    displaySymbol: str
    name: str = ""
    assetType: str
    assetTypeLabel: str
    totalShares: float
    closedShares: float
    totalCost: float
    totalProceeds: float
    realizedPL: float
    realizedPLPercent: float
    averageBuyPrice: float
    averageSellPrice: float
    currency: str
    originalCurrency: str
    lots: list[ClosedShareLot] = []


class PortfolioSummary(BaseModel):
    totalInvested: float
    totalValue: float
    openInvested: float
    closedInvested: float
    totalUnrealizedPL: float
    totalUnrealizedPLPercent: float
    totalRealizedPL: float
    totalRealizedPLPercent: float
    totalReturn: float
    totalReturnPercent: float


class PortfolioHoldingsResponse(BaseModel):
    currency: str
    exchangeRate: float
    tabId: str
    summary: PortfolioSummary
    openPositions: list[PortfolioPosition] = []
    closedPositions: list[ClosedPortfolioPosition] = []
    transactionSummaries: list[SymbolTransactionSummary] | None = None
    rawTransactions: list[Transaction] | None = None
    error: str | None = None
