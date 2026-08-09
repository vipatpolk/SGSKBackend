import httpx
import asyncio
from typing import Dict, List, Any
import urllib.parse
from models.transaction import PriceData
from services.nav_service import NavService
from utils.format_utils import to_yahoo_symbol, resolve_quote_currency

class PriceService:
    def __init__(self):
        self.nav_service = NavService()
        self.client = httpx.AsyncClient(follow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})

    async def fetch_prices_and_rate(self, summaries: List[Dict[str, str]]) -> Dict[str, Any]:
        prices_task = self.fetch_prices(summaries)
        rate_task = self.fetch_exchange_rate()
        
        prices, rate = await asyncio.gather(prices_task, rate_task)
        return {"prices": prices, "rate": rate}

    async def fetch_exchange_rate(self, from_currency: str = 'USD', to_currency: str = 'THB') -> float:
        if from_currency == to_currency:
            return 1.0
            
        pair = f"{from_currency}{to_currency}=X"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(pair)}?range=1d&interval=1d&includePrePost=false"
        try:
            res = await self.client.get(url)
            res.raise_for_status()
            meta = res.json().get('chart', {}).get('result', [{}])[0].get('meta', {})
            return self._extract_yahoo_price(meta)
        except Exception:
            return 0.0

    @staticmethod
    def _is_crypto(s: Dict[str, str]) -> bool:
        return s.get('assetType') == 'crypto' or s.get('symbol', '').upper().endswith('.CRYPTO')

    @staticmethod
    def _is_fund(s: Dict[str, str]) -> bool:
        return s.get('assetType') == 'mutual-fund' or s.get('symbol', '').upper().endswith('.BKFUND')

    def _extract_yahoo_price(self, meta: dict) -> float:
        return meta.get('regularMarketPrice') or meta.get('chartPreviousClose') or meta.get('previousClose') or 0.0

    async def fetch_prices(self, summaries: List[Dict[str, str]]) -> Dict[str, PriceData]:
        if not summaries:
            return {}

        stock_symbols = list(set([s['symbol'] for s in summaries if not self._is_fund(s) and not self._is_crypto(s)]))
        crypto_symbols = list(set([s['symbol'] for s in summaries if self._is_crypto(s)]))
        fund_symbols = list(set([s['symbol'] for s in summaries if self._is_fund(s)]))

        tasks = []
        if stock_symbols: tasks.append(self.fetch_stock_prices(stock_symbols))
        if crypto_symbols: tasks.append(self.fetch_crypto_prices(crypto_symbols))
        if fund_symbols: tasks.append(self.nav_service.fetch_fund_navs(fund_symbols))

        if not tasks: return {}

        results = await asyncio.gather(*tasks)
        merged = {}
        for res_map in results:
            merged.update(res_map)
        return merged

    async def _fetch_single_stock(self, symbol: str) -> Tuple[str, PriceData]:
        yahoo_symbol = to_yahoo_symbol(symbol)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(yahoo_symbol)}?range=1d&interval=1d&includePrePost=false"
        try:
            res = await self.client.get(url)
            res.raise_for_status()
            meta = res.json().get('chart', {}).get('result', [{}])[0].get('meta', {})
            price = self._extract_yahoo_price(meta)
            return symbol, PriceData(
                symbol=symbol,
                name=meta.get('longName') or meta.get('shortName') or '',
                price=price,
                currency=meta.get('currency') or ''
            )
        except Exception:
            return symbol, PriceData(symbol=symbol, name='', price=0.0, currency='')

    async def fetch_stock_prices(self, symbols: List[str]) -> Dict[str, PriceData]:
        results = await asyncio.gather(*[self._fetch_single_stock(sym) for sym in symbols])
        price_map = {}
        for sym, data in results:
            if data.price > 0 or data.name:
                price_map[sym] = data
        return price_map

    async def _fetch_binance_tickers(self) -> list:
        try:
            res = await self.client.get("https://api.binance.th/api/v1/ticker/price")
            res.raise_for_status()
            return res.json()
        except Exception:
            return []

    async def _fetch_yahoo_crypto_name(self, symbol: str) -> Tuple[str, str]:
        import re
        base = re.sub(r'(?i)\.CRYPTO$', '', symbol).strip().upper()
        yahoo_symbol = f"{base}-USD"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(yahoo_symbol)}?range=1d&interval=1d&includePrePost=false"
        try:
            res = await self.client.get(url)
            res.raise_for_status()
            meta = res.json().get('chart', {}).get('result', [{}])[0].get('meta', {})
            return symbol, meta.get('longName') or meta.get('shortName') or ''
        except Exception:
            return symbol, ''

    def _resolve_crypto_price(self, raw_symbol: str, tickers: list) -> Tuple[float, str]:
        import re
        base = re.sub(r'(?i)\.CRYPTO$', '', raw_symbol).strip().upper()
        if not base or not tickers:
            return 0.0, ''
        matches = []
        for t in tickers:
            sym = t.get('symbol', '').upper()
            price = float(t.get('price', 0))
            if price <= 0: continue
            if sym == base:
                quote = 'THB' if sym.endswith('THB') else ('USD' if 'USD' in sym else '')
                matches.append((quote, resolve_quote_currency(quote) if quote else '', price))
            elif sym.startswith(base):
                quote = sym[len(base):]
                matches.append((quote, resolve_quote_currency(quote), price))
        if not matches:
            return 0.0, ''
        
        best_match = next((m for m in matches if m[1] == 'THB'), None) or \
                     next((m for m in matches if m[1] == 'USD'), None) or matches[0]
        return best_match[2], best_match[1] or 'USD'

    async def fetch_crypto_prices(self, symbols: List[str]) -> Dict[str, PriceData]:
        tickers_task = self._fetch_binance_tickers()
        names_task = asyncio.gather(*[self._fetch_yahoo_crypto_name(sym) for sym in symbols])
        
        tickers, names = await asyncio.gather(tickers_task, names_task)
        name_map = dict(names)

        price_map = {}
        for symbol in symbols:
            price, currency = self._resolve_crypto_price(symbol, tickers)
            dynamic_name = name_map.get(symbol, '')
            price_map[symbol] = PriceData(
                symbol=symbol,
                name=dynamic_name,
                price=price,
                currency=currency
            )
        return price_map
