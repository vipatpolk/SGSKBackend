from fastapi import APIRouter, Depends

from models.transaction import SheetResult
from services.share_lot_service import ShareLotService
from utils.auth import verify_api_key

router = APIRouter(prefix="/share-lot", tags=["share-lot"], dependencies=[Depends(verify_api_key)])
service = ShareLotService()


@router.get("/sheet/{tab_id}", response_model=SheetResult)
async def fetch_sheet(tab_id: str):
    return await service.fetch_sheet(tab_id)


@router.get("/sheets", response_model=SheetResult)
async def fetch_all_sheets():
    return await service.fetch_all_sheets()
