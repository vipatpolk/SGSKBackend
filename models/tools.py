from typing import Literal

from pydantic import BaseModel, Field


class SimulatedStepModel(BaseModel):
    action: Literal["BUY", "SELL"]
    shares: float = Field(..., gt=0, description="Quantity of shares to simulate")
    price: float = Field(..., gt=0, description="Simulated order price per share")
    feePercent: float = Field(default=0.0, ge=0.0, description="Brokerage & exchange fee percentage (e.g. 0.157)")
    label: str = Field(default="", description="Optional custom step label")


class PositionSnapshotModel(BaseModel):
    symbol: str = Field(default="", description="Asset ticker or identifier")
    shares: float = Field(default=0.0, ge=0.0, description="Current holding shares")
    avgCost: float = Field(default=0.0, ge=0.0, description="Current average cost per share")
    marketPrice: float = Field(default=0.0, ge=0.0, description="Current live or reference market price")
    currency: str = Field(default="USD", description="Currency denomination (USD or THB)")
    totalCost: float | None = Field(default=None, description="Optional total invested cost basis")


class SimulateOrderRequest(BaseModel):
    initialPosition: PositionSnapshotModel | None = Field(
        default=None, description="Explicit position snapshot to start from"
    )
    symbol: str | None = Field(default=None, description="Optional symbol to auto-resolve snapshot from live portfolio")
    steps: list[SimulatedStepModel] = Field(
        default_factory=list, description="Ordered list of simulated Buy/Sell actions"
    )
    currency: str = Field(default="USD", description="Target output currency")
    taxFeePercent: float = Field(default=0.0, ge=0.0, description="Default transaction fee percentage")


class SimulationStateMetrics(BaseModel):
    totalShares: float
    averageCost: float
    totalCost: float
    marketPrice: float
    holdingValue: float
    unrealizedPL: float
    unrealizedPLPercent: float
    realizedPL: float


class SimulationDeltaMetrics(BaseModel):
    shares: float
    sharesPercent: float
    averageCost: float
    averageCostPercent: float
    totalCost: float
    totalCostPercent: float
    holdingValue: float
    holdingValuePercent: float
    unrealizedPL: float
    unrealizedPLPercent: float
    breakevenDistanceInitial: float
    breakevenDistanceSimulated: float
    realizedPL: float


class SimulateOrderResponse(BaseModel):
    initial: SimulationStateMetrics
    simulated: SimulationStateMetrics
    delta: SimulationDeltaMetrics
    steps: list[SimulatedStepModel]
    totalCapitalOutlay: float
    totalProceeds: float
    totalFees: float
    currency: str


class SolveTargetCostRequest(BaseModel):
    initialPosition: PositionSnapshotModel | None = Field(default=None, description="Current position snapshot")
    symbol: str | None = Field(default=None, description="Optional symbol to auto-resolve snapshot from live portfolio")
    targetAvgCost: float = Field(..., gt=0, description="Target average cost per share to achieve")
    purchasePrice: float = Field(..., gt=0, description="Expected purchase price per share")
    feePercent: float = Field(default=0.0, ge=0.0, description="Brokerage fee percentage (e.g. 0.157)")
    currency: str = Field(default="USD", description="Currency denomination")


class SolveTargetCostResponse(BaseModel):
    isValid: bool
    errorMessage: str = ""
    requiredShares: float = 0.0
    requiredCapital: float = 0.0
    feeAmount: float = 0.0
    totalOutlay: float = 0.0
    achievedAvgCost: float = 0.0
    newTotalShares: float = 0.0
    newTotalCost: float = 0.0
    currency: str = "USD"


CompoundingFrequency = Literal[
    "daily",
    "weekly",
    "biweekly",
    "semimonthly",
    "monthly",
    "quarterly",
    "semiannually",
    "annually",
]

TvmSolveMode = Literal["FV", "PMT", "PV", "N", "RATE"]
PaymentTiming = Literal["end", "beginning"]


class TvmScheduleEntryModel(BaseModel):
    period: int
    year: int
    startBalance: float
    contributions: float
    interestEarned: float
    endBalance: float
    totalContributionsToDate: float
    totalInterestToDate: float


class TvmCalculateRequest(BaseModel):
    mode: TvmSolveMode = Field(default="FV", description="Variable to solve for: FV, PMT, PV, N, RATE")
    presentValue: float = Field(default=0.0, ge=0.0, description="Initial lump sum capital / PV")
    payment: float = Field(default=0.0, ge=0.0, description="Periodic recurring payment / PMT")
    annualRatePct: float = Field(default=8.0, ge=0.0, description="Annual nominal interest rate (%)")
    years: float = Field(default=10.0, ge=0.0, description="Total investment horizon in years")
    compounding: CompoundingFrequency = Field(default="monthly", description="Compounding frequency per year")
    timing: PaymentTiming = Field(default="end", description="Payment timing: end (ordinary) or beginning (due)")
    targetFutureValue: float | None = Field(
        default=None, ge=0.0, description="Target Future Value when solving for PMT, PV, N, or RATE"
    )
    currency: str = Field(default="USD", description="Currency denomination (USD or THB)")


class TvmCalculateResponse(BaseModel):
    mode: TvmSolveMode
    futureValue: float
    presentValue: float
    payment: float
    annualRatePct: float
    years: float
    compounding: CompoundingFrequency
    compoundingPeriodsPerYear: int
    totalPeriods: int
    totalPrincipal: float
    totalContributions: float
    totalInvested: float
    totalInterestEarned: float
    effectiveAnnualRatePct: float
    multiplier: float
    currency: str = "USD"
    schedule: list[TvmScheduleEntryModel] = Field(default_factory=list)
    isValid: bool = True
    errorMessage: str = ""


RebalanceMode = Literal["standard", "no-sell"]
NoSellSubMode = Literal["min-inflow", "custom-deposit"]
RebalanceAction = Literal["BUY", "SELL", "BALANCED"]


class SymbolRebalanceInputModel(BaseModel):
    symbol: str
    targetPercent: float = Field(default=0.0, ge=0.0, le=100.0)


class RebalanceTradeOrderModel(BaseModel):
    id: str
    symbol: str
    displaySymbol: str
    name: str
    assetType: str
    action: Literal["BUY", "SELL"]
    shares: float
    price: float
    amount: float
    currency: str = "USD"


class SymbolRebalanceItemModel(BaseModel):
    symbol: str
    displaySymbol: str
    name: str
    assetType: str
    assetTypeLabel: str
    currency: str
    currentShares: float
    currentPrice: float
    currentValue: float
    currentClassPercent: float
    currentPortfolioPercent: float
    targetPercent: float
    targetValue: float
    action: RebalanceAction
    deltaValue: float
    deltaShares: float
    color: str
    isAnchorPosition: bool = False


class AssetClassRebalanceGroupModel(BaseModel):
    assetType: str
    label: str
    color: str
    currentValue: float
    currentPortfolioPercent: float
    targetTotalPercent: float
    isValid: bool
    minInflowRequired: float
    totalBuyAmount: float
    totalSellAmount: float
    symbols: list[SymbolRebalanceItemModel] = Field(default_factory=list)


class RebalanceCalculateRequest(BaseModel):
    mode: RebalanceMode = Field(default="standard")
    noSellSubMode: NoSellSubMode = Field(default="min-inflow")
    customCashDeposit: float = Field(default=0.0, ge=0.0)
    targetAllocations: dict[str, float] = Field(default_factory=dict, description="Map of symbol -> target % in class")
    currency: str = Field(default="USD")


class RebalanceCalculateResponse(BaseModel):
    mode: RebalanceMode
    noSellSubMode: NoSellSubMode = "min-inflow"
    currency: str = "USD"
    totalCurrentPortfolioValue: float

    totalTargetPortfolioValue: float
    cashContribution: float
    totalBuyAmount: float
    totalSellAmount: float
    netCashDifference: float
    groups: list[AssetClassRebalanceGroupModel] = Field(default_factory=list)
    orders: list[RebalanceTradeOrderModel] = Field(default_factory=list)
    isValid: bool = True
    errorMessage: str = ""


