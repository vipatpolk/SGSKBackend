from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any
from services.price_service import PriceService

router = APIRouter(prefix="/price", tags=["price"])
service = PriceService()

class SummariesRequest(BaseModel):
    summaries: List[Dict[str, str]]

@router.post("/fetch-prices")
async def fetch_prices_and_rate(req: SummariesRequest):
    return await service.fetch_prices_and_rate(req.summaries)

@router.get("/exchange-rate")
async def fetch_exchange_rate(from_currency: str = "USD", to_currency: str = "THB"):
    rate = await service.fetch_exchange_rate(from_currency, to_currency)
    return {"rate": rate}
