import asyncio

import httpx


async def f():
    async with httpx.AsyncClient() as client:
        res = await client.post("http://localhost:8000/price/fetch-prices", json={"summaries": [{"symbol": "VOO"}]})
        print(res.status_code)
        print(res.json())


asyncio.run(f())
