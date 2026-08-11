
from fastapi import APIRouter
from pydantic import BaseModel

from services.nav_service import NavService

router = APIRouter(prefix="/nav", tags=["nav"])
service = NavService()

class NavRequest(BaseModel):
    symbols: list[str]

@router.post("/fetch")
async def fetch_navs(req: NavRequest):
    return await service.fetch_fund_navs(req.symbols)
