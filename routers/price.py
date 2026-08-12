from fastapi import APIRouter, Depends

from models.requests import SummariesRequest
from services.price_service import PriceService
from utils.auth import verify_api_key

router = APIRouter(prefix="/price", tags=["price"], dependencies=[Depends(verify_api_key)])
service = PriceService()


@router.post("/fetch-prices")
async def fetch_prices_and_rate(req: SummariesRequest):
    return await service.fetch_prices_and_rate(req.summaries)


@router.get("/exchange-rate")
async def fetch_exchange_rate(from_currency: str = "USD", to_currency: str = "THB"):
    rate = await service.fetch_exchange_rate(from_currency, to_currency)
    return {"rate": rate}
