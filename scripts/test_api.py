import asyncio
import httpx
from main import app

async def test_api():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/share-lot/sheets")
        print("Status Code:", response.status_code)
        data = response.json()
        print("Summaries length:", len(data.get("summaries", [])))

asyncio.run(test_api())
