import asyncio
from services.share_lot_service import ShareLotService

async def main():
    service = ShareLotService()
    res = await service.fetch_all_sheets()
    print("summaries len:", len(res.summaries))
    print("error:", res.error)
    print("isClosed:", res.isClosed)

asyncio.run(main())
