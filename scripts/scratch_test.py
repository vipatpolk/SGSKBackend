import asyncio

import httpx


async def main():
    async with httpx.AsyncClient(follow_redirects=True) as client:
        res = await client.get('https://query1.finance.yahoo.com/v8/finance/chart/AAPL?range=1d&interval=1d&includePrePost=false')
        print(res.status_code)
        if res.status_code == 200:
            meta = res.json().get('chart', {}).get('result', [{}])[0].get('meta', {})
            print('AAPL Name:', meta.get('longName'), meta.get('shortName'))
            print('AAPL Price:', meta.get('regularMarketPrice'))
        else:
            print(res.text)

asyncio.run(main())
