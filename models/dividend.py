from pydantic import BaseModel


class FundDividendDistribution(BaseModel):
    projId: str
    classAbbrName: str
    bookCloseDate: str
    dividendDate: str
    dividendValue: float
    lastUpdDate: str = ""


class DividendRecord(BaseModel):
    id: str
    symbol: str
    displaySymbol: str
    date: str
    assetType: str
    assetTypeLabel: str
    shares: float
    dividendPerShare: float
    grossAmount: float
    withholdingTax: float
    withholdingTaxRate: float
    netAmount: float
    currency: str
    convertedNetAmount: float
    convertedGrossAmount: float
    convertedWithholdingTax: float


class MonthlyDividendSummary(BaseModel):
    yearMonth: str  # e.g. "2026-03"
    year: int
    month: int
    grossAmount: float
    netAmount: float
    withholdingTax: float
    byAssetType: dict[str, float]
    recordCount: int


class AnnualDividendSummary(BaseModel):
    year: int
    grossAmount: float
    netAmount: float
    withholdingTax: float
    byAssetType: dict[str, float]
    recordCount: int
    monthlyBreakdown: list[MonthlyDividendSummary] = []


class AssetTypeDividendSummary(BaseModel):
    assetType: str
    assetTypeLabel: str
    totalGrossDividends: float
    totalNetDividends: float
    totalWithholdingTax: float
    percentageOfTotal: float
    symbolCount: int
    recordCount: int
    totalCostBasis: float = 0.0
    currentValue: float = 0.0
    projectedAnnualDividends: float = 0.0
    yieldOnCostPercent: float = 0.0
    currentYieldPercent: float = 0.0


class SymbolDividendSummary(BaseModel):
    symbol: str
    displaySymbol: str
    name: str = ""
    assetType: str
    assetTypeLabel: str
    currency: str
    totalGrossDividends: float
    totalNetDividends: float
    totalWithholdingTax: float
    convertedNetDividends: float
    convertedGrossDividends: float
    convertedWithholdingTax: float
    dividendCount: int
    firstDividendDate: str = ""
    lastDividendDate: str = ""
    currentShares: float = 0.0
    currentCostBasis: float = 0.0
    currentValue: float = 0.0
    trailingAnnualDPS: float = 0.0
    currentYieldPercent: float = 0.0
    yieldOnCostPercent: float = 0.0
    projectedAnnualIncome: float = 0.0
    recentDistributions: list[FundDividendDistribution] = []


class PortfolioDividendResponse(BaseModel):
    currency: str
    exchangeRate: float
    totalGrossDividends: float
    totalNetDividends: float
    totalWithholdingTax: float
    effectiveTaxRate: float
    projectedAnnualDividends: float
    portfolioDividendYield: float
    portfolioYieldOnCost: float
    annualDividends: list[AnnualDividendSummary] = []
    monthlyDividends: list[MonthlyDividendSummary] = []
    assetTypeSummaries: list[AssetTypeDividendSummary] = []
    symbolSummaries: list[SymbolDividendSummary] = []
    records: list[DividendRecord] = []
    error: str | None = None
