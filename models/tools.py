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
