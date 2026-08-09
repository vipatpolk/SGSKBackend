from fastapi import APIRouter
from services.share_lot_service import ShareLotService
from models.transaction import SheetResult

router = APIRouter(prefix="/share-lot", tags=["share-lot"])
service = ShareLotService()

@router.get("/sheet/{tab_id}", response_model=SheetResult)
async def fetch_sheet(tab_id: str):
    return await service.fetch_sheet(tab_id)

@router.get("/sheets", response_model=SheetResult)
async def fetch_all_sheets():
    return await service.fetch_all_sheets()
