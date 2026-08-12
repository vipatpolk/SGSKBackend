from fastapi import APIRouter, Depends

from models.requests import NavRequest
from services.nav_service import NavService
from utils.auth import verify_api_key

router = APIRouter(prefix="/nav", tags=["nav"], dependencies=[Depends(verify_api_key)])
service = NavService()


@router.post("/fetch")
async def fetch_navs(req: NavRequest):
    return await service.fetch_fund_navs(req.symbols)
