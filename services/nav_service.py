import asyncio
import re
import urllib.parse
from datetime import datetime, timedelta
from typing import Any, cast

import httpx

from config.settings import get_settings
from models.transaction import PriceData
from utils.cache import singleflight, ttl_cache
from utils.http_client import get_http_client, get_sec_semaphore

SEC_API_CONFIG = {
    "baseUrl": "https://api.sec.or.th/v2/fund",
}


class NavService:
    def __init__(self, client: httpx.AsyncClient | None = None):
        settings = get_settings()
        self.headers = {
            "Ocp-Apim-Subscription-Key": settings.sec_subscription_key,
            "Accept": "application/json",
        }
        self._custom_client = client

    @property
    def client(self) -> httpx.AsyncClient:
        return self._custom_client or get_http_client()

    async def fetch_fund_navs(self, symbols: list[str]) -> dict[str, PriceData]:
        unique_symbols = list(set(symbols))
        if not unique_symbols:
            return {}

        results = await asyncio.gather(*[self.fetch_single_fund_nav(sym) for sym in unique_symbols])

        price_map = {}
        for r in results:
            if r["data"].price > 0 or (
                r["data"].name and r["data"].name != r["originalSymbol"] and r["data"].name != r["data"].symbol
            ):
                price_map[r["originalSymbol"]] = r["data"]

        return price_map

    async def fetch_pvd_policies(self, proj_id: str | None = None) -> dict[str, dict[str, Any]]:
        settings = get_settings()
        target_proj_id = proj_id or settings.sec_pvd_proj_id
        cache_key = f"sec_pvd_policies_{target_proj_id}"
        cached = ttl_cache.get(cache_key)
        if cached is not None:
            return cast(dict[str, dict[str, Any]], cached)

        async def _do_fetch() -> dict[str, dict[str, Any]]:
            c = ttl_cache.get(cache_key)
            if c is not None:
                return cast(dict[str, dict[str, Any]], c)

            url = f"{settings.sec_pvd_base_url}/factsheet/{target_proj_id}/policy"
            try:
                async with get_sec_semaphore():
                    res = await self.client.get(url, headers=self.headers)
                res.raise_for_status()
                raw_list = res.json()
                if not isinstance(raw_list, list):
                    return {}

                policy_map: dict[str, dict[str, Any]] = {}
                for item in raw_list:
                    sub_id = item.get("sub_policy_id")
                    if sub_id:
                        key = str(sub_id).strip().upper()
                        policy_map[key] = {
                            "subPolicyId": sub_id,
                            "name": item.get("sub_policy_name") or "",
                            "policyName": item.get("policy_name") or "",
                            "aimcType": item.get("aimc_type") or "",
                            "riskLevel": item.get("risk_level") or "",
                            "objective": item.get("objective") or "",
                        }

                ttl_cache.set(cache_key, policy_map, ttl=86400.0)
                return policy_map
            except Exception:
                return {}

        return await singleflight.execute(f"fetch_pvd_policies_{target_proj_id}", _do_fetch)

    async def fetch_single_fund_nav(self, symbol: str) -> dict[str, Any]:
        cache_key = f"sec_nav_single_{symbol}"
        cached = ttl_cache.get(cache_key)
        if cached is not None:
            return cast(dict[str, Any], cached)

        async def _do_fetch_nav() -> dict[str, Any]:
            c = ttl_cache.get(cache_key)
            if c is not None:
                return cast(dict[str, Any], c)

            clean_symbol = re.sub(r"(?i)\.(FUND|BKFUND)$", "", symbol).strip()
            sym_upper = clean_symbol.upper()

            profile = await self.fetch_fund_profile(clean_symbol, sym_upper)
            if not profile or not profile.get("proj_id"):
                res_empty = {
                    "originalSymbol": symbol,
                    "data": PriceData(symbol=symbol, name=clean_symbol, price=0.0, currency="THB"),
                }
                return res_empty

            fund = {
                "projId": profile["proj_id"],
                "name": profile.get("proj_name_en") or profile.get("proj_name_th") or clean_symbol,
                "targetClass": profile.get("fund_class_name"),
            }

            res = await self.fetch_fund_nav_data(symbol, clean_symbol, sym_upper, fund)
            if res["data"].price > 0:
                ttl_cache.set(cache_key, res, ttl=1800.0)
            return res

        return await singleflight.execute(f"sec_nav_single_{symbol}", _do_fetch_nav)

    async def fetch_fund_profile(self, clean_symbol: str, sym_upper: str) -> Any:
        cache_key = f"sec_profile_{clean_symbol.upper()}"
        cached = ttl_cache.get(cache_key)
        if cached is not None:
            return cached

        async def _do_fetch_profile() -> Any:
            c = ttl_cache.get(cache_key)
            if c is not None:
                return c

            try:
                url1 = (
                    f"{SEC_API_CONFIG['baseUrl']}/general-info/profiles?fund_class_name={urllib.parse.quote(clean_symbol)}"
                )
                async with get_sec_semaphore():
                    res = await self.client.get(url1, headers=self.headers)
                res.raise_for_status()
                class_items = []
                if res.status_code != 204:
                    data = res.json()
                    class_items = data.get("items", [])

                for i in class_items:
                    if (
                        str(i.get("fund_class_name")).upper() == sym_upper
                        or str(i.get("proj_abbr_name")).upper() == sym_upper
                    ):
                        ttl_cache.set(cache_key, i, ttl=86400.0)
                        return i

                url2 = f"{SEC_API_CONFIG['baseUrl']}/general-info/profiles?project_info={urllib.parse.quote(clean_symbol)}"
                async with get_sec_semaphore():
                    res2 = await self.client.get(url2, headers=self.headers)
                res2.raise_for_status()
                proj_items = []
                if res2.status_code != 204:
                    data2 = res2.json()
                    proj_items = data2.get("items", [])

                if not proj_items:
                    return None

                matched = None
                for i in proj_items:
                    if str(i.get("proj_abbr_name")).upper() == sym_upper and i.get("fund_class_name") == "main":
                        matched = i
                        break
                if not matched:
                    for i in proj_items:
                        if str(i.get("fund_class_name")).upper() == sym_upper:
                            matched = i
                            break
                if not matched:
                    for i in proj_items:
                        if str(i.get("proj_abbr_name")).upper() == sym_upper:
                            matched = i
                            break
                if not matched:
                    matched = proj_items[0]

                if matched:
                    ttl_cache.set(cache_key, matched, ttl=86400.0)
                return matched
            except Exception:
                return None

        return await singleflight.execute(f"sec_profile_{clean_symbol.upper()}", _do_fetch_profile)

    async def fetch_fund_nav_data(
        self, symbol: str, clean_symbol: str, sym_upper: str, fund: dict[str, Any]
    ) -> dict[str, Any]:
        end = datetime.now()
        start = end - timedelta(days=30)

        def fmt_date(d: datetime) -> str:
            return d.strftime("%Y-%m-%d")

        url = f"{SEC_API_CONFIG['baseUrl']}/daily-info/nav?proj_id={urllib.parse.quote(fund['projId'])}&start_nav_date={fmt_date(start)}&end_nav_date={fmt_date(end)}"
        try:
            async with get_sec_semaphore():
                res = await self.client.get(url, headers=self.headers)
            res.raise_for_status()
            data_raw = res.json()
            data = data_raw if isinstance(data_raw, list) else data_raw.get("items", [])

            if not data:
                return {
                    "originalSymbol": symbol,
                    "data": PriceData(symbol=symbol, name=fund["name"], price=0.0, currency="THB"),
                }

            filtered_data = [
                d
                for d in data
                if str(d.get("fund_class_name")).upper() == str(fund.get("targetClass") or clean_symbol).upper()
            ]
            if not filtered_data and fund.get("targetClass") != "main":
                filtered_data = [d for d in data if str(d.get("fund_class_name")).upper() == sym_upper]
            if not filtered_data:
                filtered_data = [d for d in data if d.get("fund_class_name") == "main"]
            if not filtered_data:
                filtered_data = data

            filtered_data.sort(key=lambda x: x["nav_date"], reverse=True)
            latest = filtered_data[0]
            nav = latest.get("last_val", 0)

            return {
                "originalSymbol": symbol,
                "data": PriceData(
                    symbol=symbol,
                    name=fund["name"],
                    price=float(nav) if nav else 0.0,
                    currency="THB",
                ),
            }
        except Exception:
            return {
                "originalSymbol": symbol,
                "data": PriceData(symbol=symbol, name=fund["name"], price=0.0, currency="THB"),
            }

    async def fetch_fund_dividend_history(self, symbol: str) -> list[dict[str, Any]]:
        cache_key = f"sec_div_{symbol}"
        cached = ttl_cache.get(cache_key)
        if cached is not None:
            return cast(list[dict[str, Any]], cached)

        async def _do_fetch_div_hist() -> list[dict[str, Any]]:
            c = ttl_cache.get(cache_key)
            if c is not None:
                return cast(list[dict[str, Any]], c)

            clean_symbol = re.sub(r"(?i)\.(FUND|BKFUND)$", "", symbol).strip()
            sym_upper = clean_symbol.upper()

            headers = self.headers
            try:
                # 1. Try direct class_abbr_name query
                url1 = f"{SEC_API_CONFIG['baseUrl']}/daily-info/dividend-history?class_abbr_name={urllib.parse.quote(clean_symbol)}"
                async with get_sec_semaphore():
                    res = await self.client.get(url1, headers=headers)
                if res.status_code == 200:
                    raw_items = res.json().get("items", [])
                    if raw_items and isinstance(raw_items, list):
                        items = cast(list[dict[str, Any]], raw_items)
                        ttl_cache.set(cache_key, items, ttl=3600.0)
                        return items

                # 2. Try by fund profile proj_id fallback
                profile = await self.fetch_fund_profile(clean_symbol, sym_upper)
                if profile and profile.get("proj_id"):
                    proj_id = profile["proj_id"]
                    url2 = f"{SEC_API_CONFIG['baseUrl']}/daily-info/dividend-history?proj_id={urllib.parse.quote(proj_id)}"
                    async with get_sec_semaphore():
                        res2 = await self.client.get(url2, headers=headers)
                    if res2.status_code == 200:
                        raw_items2 = res2.json().get("items", [])
                        if isinstance(raw_items2, list):
                            items2 = cast(list[dict[str, Any]], raw_items2)
                            filtered = [
                                i
                                for i in items2
                                if str(i.get("class_abbr_name") or i.get("fund_class_name") or "").upper() == sym_upper
                            ]
                            final_res = filtered if filtered else items2
                            ttl_cache.set(cache_key, final_res, ttl=3600.0)
                            return final_res
                return []
            except Exception:
                return []

        return await singleflight.execute(f"sec_div_{symbol}", _do_fetch_div_hist)

    async def fetch_all_fund_dividends(self, symbols: list[str]) -> dict[str, list[dict[str, Any]]]:
        unique_symbols = list(set(symbols))
        if not unique_symbols:
            return {}

        results = await asyncio.gather(*[self.fetch_fund_dividend_history(sym) for sym in unique_symbols])
        return {sym: res for sym, res in zip(unique_symbols, results)}
