from fastapi import APIRouter
from services.share_lot_service import ShareLotService
from models.transaction import SheetResult

router = APIRouter(prefix="/share-lot", tags=["share-lot"])
service = ShareLotService()

@router.get("/sheet/{gid}", response_model=SheetResult)
async def fetch_sheet(gid: str):
    return await service.fetch_sheet(gid)

@router.get("/sheets", response_model=SheetResult)
async def fetch_all_sheets():
    return await service.fetch_all_sheets()
