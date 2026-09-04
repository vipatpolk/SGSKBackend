import asyncio
import re
import time
import urllib.parse
from typing import Any, cast

import httpx

from models.transaction import PriceData
from services.nav_service import NavService
from utils.cache import ttl_cache
from utils.format_utils import resolve_quote_currency, to_yahoo_symbol
from utils.http_client import get_http_client, get_outbound_semaphore

COMMON_CRYPTO_NAMES: dict[str, str] = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "SOL": "Solana",
    "USDT": "Tether USDt",
    "BNB": "BNB",
    "XRP": "XRP",
    "ADA": "Cardano",
    "DOGE": "Dogecoin",
    "DOT": "Polkadot",
    "AVAX": "Avalanche",
}


class PriceService:
    def __init__(self, client: httpx.AsyncClient | None = None, nav_service: NavService | None = None):
        self.nav_service = nav_service or NavService(client=client)
        self._custom_client = client

    @property
    def client(self) -> httpx.AsyncClient:
        return self._custom_client or get_http_client()

    async def fetch_prices_and_rate(self, summaries: list[dict[str, str]]) -> dict[str, Any]:
        prices_task = self.fetch_prices(summaries)
        rate_task = self.fetch_exchange_rate()

        prices, rate = await asyncio.gather(prices_task, rate_task)
        return {"prices": prices, "rate": rate}

    async def fetch_exchange_rate(self, from_currency: str = "USD", to_currency: str = "THB") -> float:
        if from_currency == to_currency:
            return 1.0

        cache_key = f"rate_{from_currency}_{to_currency}"
        cached = ttl_cache.get(cache_key)
        if cached is not None:
            return cast(float, cached)

        pair = f"{from_currency}{to_currency}=X"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(pair)}?range=1d&interval=1d&includePrePost=false"
        try:
            async with get_outbound_semaphore():
                res = await self.client.get(url)
            res.raise_for_status()
            meta = res.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
            rate = self._extract_yahoo_price(meta)
            if rate > 0:
                ttl_cache.set(cache_key, rate, ttl=300.0)
            return rate
        except Exception:
            return 0.0

    @staticmethod
    def _is_crypto(s: dict[str, str]) -> bool:
        return s.get("assetType") == "crypto" or s.get("symbol", "").upper().endswith(".CRYPTO")

    @staticmethod
    def _is_fund(s: dict[str, str]) -> bool:
        sym = s.get("symbol", "").upper()
        return s.get("assetType") == "mutual-fund" or sym.endswith(".FUND") or sym.endswith(".BKFUND")

    def _extract_yahoo_price(self, meta: dict[str, Any]) -> float:
        return meta.get("regularMarketPrice") or meta.get("chartPreviousClose") or meta.get("previousClose") or 0.0

    async def fetch_prices(self, summaries: list[dict[str, str]]) -> dict[str, PriceData]:
        if not summaries:
            return {}

        stock_symbols = list(set([s["symbol"] for s in summaries if not self._is_fund(s) and not self._is_crypto(s)]))
        crypto_symbols = list(set([s["symbol"] for s in summaries if self._is_crypto(s)]))
        fund_symbols = list(set([s["symbol"] for s in summaries if self._is_fund(s)]))

        tasks = []
        if stock_symbols:
            tasks.append(self.fetch_stock_prices(stock_symbols))
        if crypto_symbols:
            tasks.append(self.fetch_crypto_prices(crypto_symbols))
        if fund_symbols:
            tasks.append(self.nav_service.fetch_fund_navs(fund_symbols))

        if not tasks:
            return {}

        results = await asyncio.gather(*tasks)
        merged = {}
        for res_map in results:
            merged.update(res_map)
        return merged

    async def _fetch_single_stock(self, symbol: str) -> tuple[str, PriceData]:
        cache_key = f"stock_price_{symbol}"
        cached = ttl_cache.get(cache_key)
        if cached is not None:
            return symbol, cached

        yahoo_symbol = to_yahoo_symbol(symbol)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(yahoo_symbol)}?range=1d&interval=1d&includePrePost=false"
        try:
            async with get_outbound_semaphore():
                res = await self.client.get(url)
            res.raise_for_status()
            meta = res.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
            price = self._extract_yahoo_price(meta)
            data = PriceData(
                symbol=symbol,
                name=meta.get("longName") or meta.get("shortName") or "",
                price=price,
                currency=meta.get("currency") or "",
            )
            if price > 0 or data.name:
                ttl_cache.set(cache_key, data, ttl=60.0)
            return symbol, data
        except Exception:
            return symbol, PriceData(symbol=symbol, name="", price=0.0, currency="")

    async def fetch_stock_prices(self, symbols: list[str]) -> dict[str, PriceData]:
        results = await asyncio.gather(*[self._fetch_single_stock(sym) for sym in symbols])
        price_map = {}
        for sym, data in results:
            if data.price > 0 or data.name:
                price_map[sym] = data
        return price_map

    async def _fetch_binance_tickers(self) -> Any:
        cache_key = "binance_tickers"
        cached = ttl_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            async with get_outbound_semaphore():
                res = await self.client.get("https://api.binance.th/api/v1/ticker/price")
            res.raise_for_status()
            data = res.json()
            ttl_cache.set(cache_key, data, ttl=30.0)
            return data
        except Exception:
            return []

    async def _fetch_yahoo_crypto_name(self, symbol: str) -> tuple[str, str]:
        base = re.sub(r"(?i)\.CRYPTO$", "", symbol).strip().upper()
        if base in COMMON_CRYPTO_NAMES:
            return symbol, COMMON_CRYPTO_NAMES[base]

        cache_key = f"crypto_name_{symbol}"
        cached = ttl_cache.get(cache_key)
        if cached is not None:
            return symbol, cached

        yahoo_symbol = f"{base}-USD"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(yahoo_symbol)}?range=1d&interval=1d&includePrePost=false"
        try:
            async with get_outbound_semaphore():
                res = await self.client.get(url)
            res.raise_for_status()
            meta = res.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
            name = meta.get("longName") or meta.get("shortName") or ""
            if name:
                ttl_cache.set(cache_key, name, ttl=86400.0)
            return symbol, name
        except Exception:
            return symbol, ""

    def _resolve_crypto_price(self, raw_symbol: str, tickers: list[dict[str, Any]]) -> tuple[float, str]:
        base = re.sub(r"(?i)\.CRYPTO$", "", raw_symbol).strip().upper()
        if not base or not tickers:
            return 0.0, ""
        matches = []
        for t in tickers:
            sym = t.get("symbol", "").upper()
            price = float(t.get("price", 0))
            if price <= 0:
                continue
            if sym == base:
                quote = "THB" if sym.endswith("THB") else ("USD" if "USD" in sym else "")
                matches.append((quote, resolve_quote_currency(quote) if quote else "", price))
            elif sym.startswith(base):
                quote = sym[len(base) :]
                matches.append((quote, resolve_quote_currency(quote), price))
        if not matches:
            return 0.0, ""

        best_match = (
            next((m for m in matches if m[1] == "THB"), None)
            or next((m for m in matches if m[1] == "USD"), None)
            or matches[0]
        )
        return best_match[2], best_match[1] or "USD"

    async def fetch_crypto_prices(self, symbols: list[str]) -> dict[str, PriceData]:
        tickers_task = self._fetch_binance_tickers()
        names_task = asyncio.gather(*[self._fetch_yahoo_crypto_name(sym) for sym in symbols])

        tickers, names = await asyncio.gather(tickers_task, names_task)
        name_map = dict(names)
        price_map = {}
        for symbol in symbols:
            price, currency = self._resolve_crypto_price(symbol, tickers)
            dynamic_name = name_map.get(symbol, "")
            price_map[symbol] = PriceData(symbol=symbol, name=dynamic_name, price=price, currency=currency)
        return price_map

    async def _fetch_single_stock_dividends(self, symbol: str) -> tuple[str, dict[str, Any]]:
        cache_key = f"stock_div_{symbol}"
        cached = ttl_cache.get(cache_key)
        if cached is not None:
            return symbol, cached

        yahoo_symbol = to_yahoo_symbol(symbol)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(yahoo_symbol)}?range=5y&interval=1mo&events=div"
        try:
            async with get_outbound_semaphore():
                res = await self.client.get(url)
            res.raise_for_status()
            result = res.json().get("chart", {}).get("result", [{}])[0]
            events = result.get("events", {})
            div_map = events.get("dividends", {})
            div_list = []
            now_ts = time.time()
            one_year_ago_ts = now_ts - (365 * 24 * 3600)
            trailing_12m = 0.0
            if isinstance(div_map, dict):
                for ts_str, d in div_map.items():
                    amt = float(d.get("amount", 0.0))
                    dt = d.get("date", int(ts_str) if ts_str.isdigit() else 0)
                    div_list.append({"amount": amt, "date": dt})
                    if dt >= one_year_ago_ts:
                        trailing_12m += amt

            div_list.sort(key=lambda x: x.get("date", 0), reverse=True)
            res_data = {"trailing_12m_dps": trailing_12m, "dividends": div_list}
            ttl_cache.set(cache_key, res_data, ttl=3600.0)
            return symbol, res_data
        except Exception:
            return symbol, {"trailing_12m_dps": 0.0, "dividends": []}

    async def fetch_stock_dividends(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        unique = list(
            set([s for s in symbols if not self._is_crypto({"symbol": s}) and not self._is_fund({"symbol": s})])
        )
        if not unique:
            return {}
        results = await asyncio.gather(*[self._fetch_single_stock_dividends(sym) for sym in unique])
        return dict(results)
