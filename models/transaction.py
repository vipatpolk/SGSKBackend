from pydantic import BaseModel
from typing import List, Optional, Dict

class Transaction(BaseModel):
    symbol: str
    date: str
    quantity: float
    price: float
    currency: str
    assetType: str

class ShareLot(BaseModel):
    symbol: str
    purchaseDate: str
    quantity: float
    costBasis: float
    totalCost: float
    assetType: str

class ClosedShareLot(BaseModel):
    symbol: str
    purchaseDate: str
    closeDate: str
    quantity: float
    costBasis: float
    sellPrice: float
    totalCost: float
    totalProceeds: float
    realizedPL: float
    realizedPLPercent: float
    currency: str
    assetType: str

class SymbolSummary(BaseModel):
    symbol: str
    totalShares: float
    totalCost: float
    averageCost: float
    currency: str
    lots: List[ShareLot]
    assetType: str

class ClosedSymbolSummary(BaseModel):
    symbol: str
    totalShares: float
    closedShares: float
    totalCost: float
    totalProceeds: float
    realizedPL: float
    realizedPLPercent: float
    averageBuyPrice: float
    averageSellPrice: float
    currency: str
    lots: List[ClosedShareLot]
    assetType: str

class SymbolTransaction(BaseModel):
    id: str
    symbol: str
    date: str
    type: str # 'BUY' | 'SELL'
    quantity: float
    rawQuantity: float
    price: float
    totalAmount: float
    currency: str
    assetType: str
    runningShares: float
    runningTotalCost: float
    runningAverageCost: float
    realizedPL: Optional[float] = None
    realizedPLPercent: Optional[float] = None

class SymbolTransactionSummary(BaseModel):
    symbol: str
    assetType: str
    currency: str
    totalTransactions: int
    buyCount: int
    sellCount: int
    totalBuyShares: float
    totalSellShares: float
    totalBuyAmount: float
    totalSellAmount: float
    averageBuyPrice: float
    averageSellPrice: float
    netShares: float
    netInvested: float
    currentStatus: str # 'OPEN' | 'CLOSED'
    realizedPL: float
    realizedPLPercent: float
    firstTradeDate: str
    lastTradeDate: str
    transactions: List[SymbolTransaction]

class SheetResult(BaseModel):
    summaries: List[SymbolSummary]
    closedSummaries: List[ClosedSymbolSummary]
    transactionSummaries: Optional[List[SymbolTransactionSummary]] = None
    rawTransactions: Optional[List[Transaction]] = None
    totalCostByCurrency: Dict[str, float]
    totalProceedsByCurrency: Dict[str, float]
    totalRealizedPLByCurrency: Dict[str, float]
    totalSymbols: int
    totalLots: int
    error: Optional[str] = None
    isClosed: Optional[bool] = False

class PriceData(BaseModel):
    symbol: str
    name: Optional[str] = ""
    price: float
    currency: str
