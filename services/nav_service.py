import asyncio
import urllib.parse
from datetime import datetime, timedelta
from typing import Any

import httpx

from models.transaction import PriceData

SEC_API_CONFIG = {
    'subscriptionKey': '5544171ad4944dde9454d20054233891',
    'baseUrl': 'https://api.sec.or.th/v2/fund',
}

class NavService:
    def __init__(self):
        self.headers = {
            'Ocp-Apim-Subscription-Key': SEC_API_CONFIG['subscriptionKey'],
            'Accept': 'application/json'
        }
        self.client = httpx.AsyncClient(headers=self.headers)

    async def fetch_fund_navs(self, symbols: list[str]) -> dict[str, PriceData]:
        unique_symbols = list(set(symbols))
        if not unique_symbols:
            return {}

        results = await asyncio.gather(*[self.fetch_single_fund_nav(sym) for sym in unique_symbols])

        price_map = {}
        for r in results:
            if r['data'].price > 0 or (r['data'].name and r['data'].name != r['originalSymbol'] and r['data'].name != r['data'].symbol):
                price_map[r['originalSymbol']] = r['data']

        return price_map

    async def fetch_single_fund_nav(self, symbol: str) -> dict:
        import re
        clean_symbol = re.sub(r'(?i)\.BKFUND$', '', symbol).strip()
        sym_upper = clean_symbol.upper()

        profile = await self.fetch_fund_profile(clean_symbol, sym_upper)
        if not profile or not profile.get('proj_id'):
            print(f"[NavService] Could not find profile for {clean_symbol}")
            return {
                'originalSymbol': symbol,
                'data': PriceData(symbol=symbol, name=clean_symbol, price=0.0, currency='THB')
            }

        fund = {
            'projId': profile['proj_id'],
            'name': profile.get('proj_name_en') or profile.get('proj_name_th') or clean_symbol,
            'targetClass': profile.get('fund_class_name')
        }

        return await self.fetch_fund_nav_data(symbol, clean_symbol, sym_upper, fund)

    async def fetch_fund_profile(self, clean_symbol: str, sym_upper: str) -> Any:
        try:
            url1 = f"{SEC_API_CONFIG['baseUrl']}/general-info/profiles?fund_class_name={urllib.parse.quote(clean_symbol)}"
            res = await self.client.get(url1)
            res.raise_for_status()
            class_items = []
            if res.status_code != 204:
                data = res.json()
                class_items = data.get('items', [])

            for i in class_items:
                if str(i.get('fund_class_name')).upper() == sym_upper or str(i.get('proj_abbr_name')).upper() == sym_upper:
                    return i

            url2 = f"{SEC_API_CONFIG['baseUrl']}/general-info/profiles?project_info={urllib.parse.quote(clean_symbol)}"
            res2 = await self.client.get(url2)
            res2.raise_for_status()
            proj_items = []
            if res2.status_code != 204:
                data2 = res2.json()
                proj_items = data2.get('items', [])

            if not proj_items:
                return None

            for i in proj_items:
                if str(i.get('proj_abbr_name')).upper() == sym_upper and i.get('fund_class_name') == 'main':
                    return i
            for i in proj_items:
                if str(i.get('fund_class_name')).upper() == sym_upper:
                    return i
            for i in proj_items:
                if str(i.get('proj_abbr_name')).upper() == sym_upper:
                    return i

            return proj_items[0]
        except Exception as e:
            print(f"Error fetching fund profile: {e}")
            return None

    async def fetch_fund_nav_data(self, symbol: str, clean_symbol: str, sym_upper: str, fund: dict) -> dict:
        end = datetime.now()
        start = end - timedelta(days=30)
        def fmt_date(d):
            return d.strftime('%Y-%m-%d')

        url = f"{SEC_API_CONFIG['baseUrl']}/daily-info/nav?proj_id={urllib.parse.quote(fund['projId'])}&start_nav_date={fmt_date(start)}&end_nav_date={fmt_date(end)}"
        try:
            res = await self.client.get(url)
            res.raise_for_status()
            data_raw = res.json()
            data = data_raw if isinstance(data_raw, list) else data_raw.get('items', [])

            if not data:
                return {
                    'originalSymbol': symbol,
                    'data': PriceData(symbol=symbol, name=fund['name'], price=0.0, currency='THB')
                }

            filtered_data = [d for d in data if str(d.get('fund_class_name')).upper() == str(fund.get('targetClass') or clean_symbol).upper()]
            if not filtered_data and fund.get('targetClass') != 'main':
                filtered_data = [d for d in data if str(d.get('fund_class_name')).upper() == sym_upper]
            if not filtered_data:
                filtered_data = [d for d in data if d.get('fund_class_name') == 'main']
            if not filtered_data:
                filtered_data = data

            filtered_data.sort(key=lambda x: x['nav_date'], reverse=True)
            latest = filtered_data[0]
            nav = latest.get('last_val', 0)

            return {
                'originalSymbol': symbol,
                'data': PriceData(
                    symbol=symbol,
                    name=fund['name'],
                    price=float(nav) if nav else 0.0,
                    currency='THB'
                )
            }
        except Exception as e:
            print(f"Error fetching NAV data: {e}")
            return {
                'originalSymbol': symbol,
                'data': PriceData(symbol=symbol, name=fund['name'], price=0.0, currency='THB')
            }
