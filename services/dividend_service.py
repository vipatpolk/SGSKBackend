import asyncio
from datetime import datetime, timezone
from typing import Any, cast

import httpx

from models.dividend import (
    AnnualDividendSummary,
    AssetTypeDividendSummary,
    DividendRecord,
    FundDividendDistribution,
    MonthlyDividendSummary,
    PortfolioDividendResponse,
    SymbolDividendSummary,
)
from models.transaction import Transaction
from services.nav_service import NavService
from services.price_service import PriceService
from services.share_lot_service import ShareLotService
from services.valuation_service import ValuationService
from utils.cache import singleflight, ttl_cache
from utils.format_utils import convert_currency, display_symbol, get_asset_type_label

# Standard withholding tax rates
WHT_RATES: dict[str, float] = {
    "thai-stock": 0.10,
    "mutual-fund": 0.10,
    "us-stock": 0.15,
    "bond": 0.15,
}

# Asset types eligible for dividend fetching from Yahoo Finance vs overall portfolio
YAHOO_DIVIDEND_ASSET_TYPES: tuple[str, ...] = ("us-stock", "thai-stock", "bond")
DIVIDEND_ASSET_TYPES: tuple[str, ...] = ("us-stock", "thai-stock", "mutual-fund", "bond")


class DividendService:
    def __init__(
        self,
        valuation_service: ValuationService | None = None,
        share_lot_service: ShareLotService | None = None,
        price_service: PriceService | None = None,
        nav_service: NavService | None = None,
        client: httpx.AsyncClient | None = None,
    ):
        self.share_lot_service = share_lot_service or ShareLotService(client=client)
        self.price_service = price_service or PriceService(client=client)
        self.nav_service = nav_service or NavService(client=client)
        self.valuation_service = valuation_service or ValuationService(
            share_lot_service=self.share_lot_service,
            price_service=self.price_service,
            client=client,
        )

    async def get_dividend_analytics(
        self,
        currency: str = "THB",
        tab_id: str = "all",
    ) -> PortfolioDividendResponse:
        target_currency = currency.upper()
        cache_key = f"dividend_{tab_id}_{target_currency}"
        cached = ttl_cache.get(cache_key)
        if cached is not None:
            return cast(PortfolioDividendResponse, cached)

        async def _do_calc_dividend() -> PortfolioDividendResponse:
            c = ttl_cache.get(cache_key)
            if c is not None:
                return cast(PortfolioDividendResponse, c)

            # 1. Fetch portfolio holdings to get current positions, shares, cost basis, exchange rate, and transactions
            holdings_res = await self.valuation_service.get_portfolio_holdings(tab_id=tab_id, currency=target_currency)
            exchange_rate = holdings_res.exchangeRate or 1.0

            if holdings_res.error:
                return PortfolioDividendResponse(
                    currency=target_currency,
                    exchangeRate=exchange_rate,
                    totalGrossDividends=0.0,
                    totalNetDividends=0.0,
                    totalWithholdingTax=0.0,
                    effectiveTaxRate=0.0,
                    projectedAnnualDividends=0.0,
                    portfolioDividendYield=0.0,
                    portfolioYieldOnCost=0.0,
                    annualDividends=[],
                    monthlyDividends=[],
                    assetTypeSummaries=[],
                    symbolSummaries=[],
                    records=[],
                    error=holdings_res.error,
                )

            # 2. Gather non-crypto positions (open + closed) for 100% API-driven dividend fetching
            open_positions = [pos for pos in holdings_res.openPositions if pos.assetType != "crypto"]
            closed_positions = [pos for pos in (holdings_res.closedPositions or []) if pos.assetType != "crypto"]
            all_positions = open_positions + closed_positions

            stock_symbols = list(set([pos.symbol for pos in all_positions if pos.assetType in YAHOO_DIVIDEND_ASSET_TYPES]))
            fund_symbols = list(set([pos.symbol for pos in all_positions if pos.assetType == "mutual-fund"]))

            # 3. Fetch dividend histories from SEC Thailand and Yahoo Finance APIs concurrently
            stock_div_task = self.price_service.fetch_stock_dividends(stock_symbols)
            fund_div_task = self.nav_service.fetch_all_fund_dividends(fund_symbols)

            stock_div_data, fund_div_data = await asyncio.gather(stock_div_task, fund_div_task)

            res = self.calculate_dividend_analytics(
                open_positions=open_positions,
                closed_positions=closed_positions,
                raw_transactions=holdings_res.rawTransactions or [],
                stock_div_data=stock_div_data,
                fund_div_data=fund_div_data,
                exchange_rate=exchange_rate,
                target_currency=target_currency,
                total_portfolio_value=holdings_res.summary.totalValue,
                total_open_invested=holdings_res.summary.openInvested,
            )
            if not res.error:
                ttl_cache.set(cache_key, res, ttl=120.0)
            return res

        return await singleflight.execute(f"calc_dividend_{tab_id}_{target_currency}", _do_calc_dividend)

    def calculate_dividend_analytics(
        self,
        open_positions: list[Any],
        stock_div_data: dict[str, Any],
        fund_div_data: dict[str, list[dict[str, Any]]],
        exchange_rate: float,
        closed_positions: list[Any] | None = None,
        raw_transactions: list[Transaction] | None = None,
        dividend_txs: list[Transaction] | None = None,
        target_currency: str = "THB",
        total_portfolio_value: float = 0.0,
        total_open_invested: float = 0.0,
    ) -> PortfolioDividendResponse:
        closed_positions = closed_positions or []
        raw_transactions = raw_transactions or []

        # Build map of transactions by symbol for exact historical share calculation on ex-dates
        txs_by_sym: dict[str, list[Transaction]] = {}
        for tx in raw_transactions:
            if tx.assetType == "crypto":
                continue
            txs_by_sym.setdefault(tx.symbol, []).append(tx)
        for s in txs_by_sym:
            txs_by_sym[s].sort(key=lambda x: x.date)

        records: list[DividendRecord] = []
        symbol_summary_map: dict[str, SymbolDividendSummary] = {}
        monthly_map: dict[str, dict[str, Any]] = {}
        annual_map: dict[int, dict[str, Any]] = {}
        asset_type_map: dict[str, dict[str, Any]] = {
            at: {
                "gross": 0.0,
                "net": 0.0,
                "wht": 0.0,
                "symbols": set(),
                "records": 0,
                "costBasis": 0.0,
                "currentValue": 0.0,
                "projectedDividends": 0.0,
            }
            for at in DIVIDEND_ASSET_TYPES
        }

        # Process all positions purely from API dividend feeds with exact historical share balances
        all_positions = open_positions + closed_positions

        for pos in all_positions:
            sym = pos.symbol
            asset_type = pos.assetType
            if asset_type == "crypto":
                continue

            curr = pos.originalCurrency

            # Gather API distribution events
            events: list[tuple[str, float]] = []
            if asset_type in YAHOO_DIVIDEND_ASSET_TYPES:
                stock_res = stock_div_data.get(sym, {})
                for evt in stock_res.get("dividends", []):
                    amt = float(evt.get("amount", 0.0))
                    ts = evt.get("date")
                    dt_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d") if ts else ""
                    if dt_str and amt > 0:
                        events.append((dt_str, amt))
            elif asset_type == "mutual-fund":
                raw_dists = fund_div_data.get(sym, [])
                for d_item in raw_dists:
                    d_val = float(d_item.get("dividend_value", 0.0))
                    d_date = str(d_item.get("dividend_date", "")).split(" ")[0]
                    if d_date and d_val > 0:
                        events.append((d_date, d_val))

            wht_rate = WHT_RATES.get(asset_type, 0.15 if asset_type == "us-stock" else 0.10)

            for idx, (m_date, m_dps) in enumerate(events):
                # Calculate exact cumulative shares held on dividend ex-date m_date
                if sym in txs_by_sym:
                    shares_on_date = sum(tx.quantity for tx in txs_by_sym[sym] if tx.date <= m_date)
                else:
                    shares_on_date = getattr(pos, "totalShares", 0.0) or getattr(pos, "closedShares", 0.0)

                if abs(shares_on_date) < 1e-6 or shares_on_date <= 0:
                    # User did NOT hold any shares on this dividend date
                    continue

                m_gross = shares_on_date * m_dps
                m_wht = m_gross * wht_rate
                m_net = m_gross - m_wht
                m_conv_gross = convert_currency(m_gross, curr, target_currency, exchange_rate)
                m_conv_net = convert_currency(m_net, curr, target_currency, exchange_rate)
                m_conv_wht = convert_currency(m_wht, curr, target_currency, exchange_rate)

                rec = DividendRecord(
                    id=f"api-{sym}-{m_date}-{idx + 1}",
                    symbol=sym,
                    displaySymbol=display_symbol(sym),
                    date=m_date,
                    assetType=asset_type,
                    assetTypeLabel=get_asset_type_label(asset_type),
                    shares=shares_on_date,
                    dividendPerShare=m_dps,
                    grossAmount=m_gross,
                    withholdingTax=m_wht,
                    withholdingTaxRate=wht_rate * 100.0,
                    netAmount=m_net,
                    currency=curr,
                    convertedNetAmount=m_conv_net,
                    convertedGrossAmount=m_conv_gross,
                    convertedWithholdingTax=m_conv_wht,
                )
                records.append(rec)

                # Monthly Aggregation
                ym = m_date[:7] if len(m_date) >= 7 else "Unknown"
                year = int(m_date[:4]) if len(m_date) >= 4 and m_date[:4].isdigit() else 0
                month = int(m_date[5:7]) if len(m_date) >= 7 and m_date[5:7].isdigit() else 0

                if ym not in monthly_map:
                    monthly_map[ym] = {
                        "yearMonth": ym,
                        "year": year,
                        "month": month,
                        "gross": 0.0,
                        "net": 0.0,
                        "wht": 0.0,
                        "byAssetType": {},
                        "recordCount": 0,
                    }
                monthly_map[ym]["gross"] += m_conv_gross
                monthly_map[ym]["net"] += m_conv_net
                monthly_map[ym]["wht"] += m_conv_wht
                monthly_map[ym]["recordCount"] += 1
                monthly_map[ym]["byAssetType"][asset_type] = (
                    monthly_map[ym]["byAssetType"].get(asset_type, 0.0) + m_conv_net
                )

                # Annual Aggregation
                if year not in annual_map:
                    annual_map[year] = {
                        "year": year,
                        "gross": 0.0,
                        "net": 0.0,
                        "wht": 0.0,
                        "byAssetType": {},
                        "recordCount": 0,
                        "monthlyBreakdown": {},
                    }
                annual_map[year]["gross"] += m_conv_gross
                annual_map[year]["net"] += m_conv_net
                annual_map[year]["wht"] += m_conv_wht
                annual_map[year]["recordCount"] += 1
                annual_map[year]["byAssetType"][asset_type] = (
                    annual_map[year]["byAssetType"].get(asset_type, 0.0) + m_conv_net
                )

                # Asset Type Aggregation
                if asset_type in asset_type_map:
                    asset_type_map[asset_type]["gross"] += m_conv_gross
                    asset_type_map[asset_type]["net"] += m_conv_net
                    asset_type_map[asset_type]["wht"] += m_conv_wht
                    asset_type_map[asset_type]["symbols"].add(sym)
                    asset_type_map[asset_type]["records"] += 1

                # Symbol Aggregation
                if sym not in symbol_summary_map:
                    symbol_summary_map[sym] = SymbolDividendSummary(
                        symbol=sym,
                        displaySymbol=pos.displaySymbol,
                        name=pos.name,
                        assetType=asset_type,
                        assetTypeLabel=pos.assetTypeLabel,
                        currency=curr,
                        totalGrossDividends=0.0,
                        totalNetDividends=0.0,
                        totalWithholdingTax=0.0,
                        convertedNetDividends=0.0,
                        convertedGrossDividends=0.0,
                        convertedWithholdingTax=0.0,
                        dividendCount=0,
                        firstDividendDate=m_date,
                        lastDividendDate=m_date,
                    )

                sym_s = symbol_summary_map[sym]
                sym_s.totalGrossDividends += m_gross
                sym_s.totalNetDividends += m_net
                sym_s.totalWithholdingTax += m_wht
                sym_s.convertedGrossDividends += m_conv_gross
                sym_s.convertedNetDividends += m_conv_net
                sym_s.convertedWithholdingTax += m_conv_wht
                sym_s.dividendCount += 1
                if not sym_s.firstDividendDate or m_date < sym_s.firstDividendDate:
                    sym_s.firstDividendDate = m_date
                if not sym_s.lastDividendDate or m_date > sym_s.lastDividendDate:
                    sym_s.lastDividendDate = m_date

        # Enrich Symbol Summaries with Open Positions, Market Yields, and Forward Projections
        projected_annual_total = 0.0

        for pos in open_positions:
            sym = pos.symbol
            asset_type = pos.assetType
            if asset_type == "crypto":
                continue

            curr = pos.originalCurrency
            shares = pos.totalShares
            cost_basis = pos.totalCost
            val = pos.holdingValue
            name = pos.name

            # Get market trailing 12M DPS and SEC distribution schedule
            trailing_dps = 0.0
            recent_dists: list[FundDividendDistribution] = []

            if asset_type == "mutual-fund":
                raw_dists = fund_div_data.get(sym, [])
                for d in raw_dists:
                    d_val = float(d.get("dividend_value", 0.0))
                    d_date = str(d.get("dividend_date", ""))
                    b_date = str(d.get("book_close_date", ""))
                    recent_dists.append(
                        FundDividendDistribution(
                            projId=d.get("proj_id", ""),
                            classAbbrName=d.get("class_abbr_name") or d.get("fund_class_name") or sym,
                            bookCloseDate=b_date.split(" ")[0] if b_date else "",
                            dividendDate=d_date.split(" ")[0] if d_date else "",
                            dividendValue=d_val,
                            lastUpdDate=str(d.get("last_upd_date", "")),
                        )
                    )
                    trailing_dps += d_val
                recent_dists.sort(key=lambda x: x.dividendDate, reverse=True)
            elif asset_type in YAHOO_DIVIDEND_ASSET_TYPES:
                stock_res = stock_div_data.get(sym, {})
                trailing_dps = float(stock_res.get("trailing_12m_dps", 0.0))

            # Forward projected annual income (calculated on current held shares)
            proj_orig_income = shares * trailing_dps
            conv_proj_income = convert_currency(proj_orig_income, curr, target_currency, exchange_rate)
            projected_annual_total += conv_proj_income

            # Yield on Cost & Current Yield
            current_price = pos.currentPrice
            avg_cost = pos.averageCost
            conv_trailing_dps = convert_currency(trailing_dps, curr, target_currency, exchange_rate)
            curr_yield_pct = (conv_trailing_dps / current_price * 100.0) if current_price > 0 else 0.0
            yoc_pct = (
                (conv_proj_income / cost_basis * 100.0)
                if cost_basis > 0
                else ((trailing_dps / avg_cost * 100.0) if avg_cost > 0 else 0.0)
            )

            if sym not in symbol_summary_map:
                symbol_summary_map[sym] = SymbolDividendSummary(
                    symbol=sym,
                    displaySymbol=pos.displaySymbol,
                    name=name,
                    assetType=asset_type,
                    assetTypeLabel=pos.assetTypeLabel,
                    currency=curr,
                    totalGrossDividends=0.0,
                    totalNetDividends=0.0,
                    totalWithholdingTax=0.0,
                    convertedNetDividends=0.0,
                    convertedGrossDividends=0.0,
                    convertedWithholdingTax=0.0,
                    dividendCount=0,
                )

            entry = symbol_summary_map[sym]
            entry.name = name
            entry.currentShares = shares
            entry.currentCostBasis = cost_basis
            entry.currentValue = val
            entry.trailingAnnualDPS = trailing_dps
            entry.currentYieldPercent = curr_yield_pct
            entry.yieldOnCostPercent = yoc_pct
            entry.projectedAnnualIncome = conv_proj_income
            entry.recentDistributions = recent_dists

            # Accumulate totals for per-asset-type Yield on Cost & Current Yield
            if asset_type in asset_type_map:
                asset_type_map[asset_type]["costBasis"] += cost_basis
                asset_type_map[asset_type]["currentValue"] += val
                asset_type_map[asset_type]["projectedDividends"] += conv_proj_income
                asset_type_map[asset_type]["symbols"].add(sym)

        # Sort records chronologically descending (newest first)
        records.sort(key=lambda x: x.date, reverse=True)

        # Asset Type Summaries
        total_net_dividends = sum(r.convertedNetAmount for r in records)
        total_gross_dividends = sum(r.convertedGrossAmount for r in records)
        total_wht = sum(r.convertedWithholdingTax for r in records)

        asset_type_summaries: list[AssetTypeDividendSummary] = []
        for at_key in DIVIDEND_ASSET_TYPES:
            at_data = asset_type_map[at_key]
            pct = (at_data["net"] / total_net_dividends * 100.0) if total_net_dividends > 0 else 0.0
            cost_b = at_data["costBasis"]
            curr_v = at_data["currentValue"]
            proj_d = at_data["projectedDividends"]
            at_yoc = (proj_d / cost_b * 100.0) if cost_b > 0 else 0.0
            at_yield = (proj_d / curr_v * 100.0) if curr_v > 0 else 0.0
            asset_type_summaries.append(
                AssetTypeDividendSummary(
                    assetType=at_key,
                    assetTypeLabel=get_asset_type_label(at_key),
                    totalGrossDividends=at_data["gross"],
                    totalNetDividends=at_data["net"],
                    totalWithholdingTax=at_data["wht"],
                    percentageOfTotal=pct,
                    symbolCount=len(at_data["symbols"]),
                    recordCount=at_data["records"],
                    totalCostBasis=cost_b,
                    currentValue=curr_v,
                    projectedAnnualDividends=proj_d,
                    yieldOnCostPercent=at_yoc,
                    currentYieldPercent=at_yield,
                )
            )

        # Monthly and Annual Summaries
        monthly_summaries = [
            MonthlyDividendSummary(
                yearMonth=v["yearMonth"],
                year=v["year"],
                month=v["month"],
                grossAmount=v["gross"],
                netAmount=v["net"],
                withholdingTax=v["wht"],
                byAssetType=v["byAssetType"],
                recordCount=v["recordCount"],
            )
            for v in monthly_map.values()
        ]
        monthly_summaries.sort(key=lambda x: x.yearMonth, reverse=True)

        annual_summaries: list[AnnualDividendSummary] = []
        for y, v in annual_map.items():
            year_months = [m for m in monthly_summaries if m.year == y]
            annual_summaries.append(
                AnnualDividendSummary(
                    year=y,
                    grossAmount=v["gross"],
                    netAmount=v["net"],
                    withholdingTax=v["wht"],
                    byAssetType=v["byAssetType"],
                    recordCount=v["recordCount"],
                    monthlyBreakdown=year_months,
                )
            )
        annual_summaries.sort(key=lambda x: x.year, reverse=True)

        # Portfolio aggregates
        effective_tax_rate = (total_wht / total_gross_dividends * 100.0) if total_gross_dividends > 0 else 0.0
        portfolio_yoc = (projected_annual_total / total_open_invested * 100.0) if total_open_invested > 0 else 0.0
        portfolio_yield = (projected_annual_total / total_portfolio_value * 100.0) if total_portfolio_value > 0 else 0.0

        # Sort symbol summaries descending by convertedNetDividends then projectedAnnualIncome
        sorted_symbols = list(symbol_summary_map.values())
        sorted_symbols.sort(key=lambda s: (s.convertedNetDividends, s.projectedAnnualIncome), reverse=True)

        return PortfolioDividendResponse(
            currency=target_currency,
            exchangeRate=exchange_rate,
            totalGrossDividends=total_gross_dividends,
            totalNetDividends=total_net_dividends,
            totalWithholdingTax=total_wht,
            effectiveTaxRate=effective_tax_rate,
            projectedAnnualDividends=projected_annual_total,
            portfolioDividendYield=portfolio_yield,
            portfolioYieldOnCost=portfolio_yoc,
            annualDividends=annual_summaries,
            monthlyDividends=monthly_summaries,
            assetTypeSummaries=asset_type_summaries,
            symbolSummaries=sorted_symbols,
            records=records,
            error=None,
        )
