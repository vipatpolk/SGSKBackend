import asyncio

from services.nav_service import NavService


async def test():
    ns = NavService()
    res = await ns.fetch_fund_navs(["tsp3-balancer.BKFUND", "k-usxndq-a(a).BKFUND", "kt-us.BKFUND"])
    for k, v in res.items():
        print(f"{k}: name='{v.name}' price={v.price}")


asyncio.run(test())
