from datetime import date, timedelta
from typing import cast

from models.performance import (
    AssetClassPerformance,
    PortfolioPerformanceResponse,
    SymbolPerformance,
)
from models.portfolio import PortfolioSummary
from services.valuation_service import ValuationService
from utils.cache import singleflight, ttl_cache
from utils.format_utils import get_asset_type_label


class PerformanceService:
    def __init__(self, valuation_service: ValuationService | None = None):
        self.valuation_service = valuation_service or ValuationService()

    def resolve_date_range(
        self,
        timeframe: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> tuple[str, str]:
        today = date.today()
        tf = (timeframe or "ALL").upper().strip()

        if tf == "CUSTOM" or (start_date and end_date and tf != "ALL"):
            return (start_date or "").strip(), (end_date or "").strip()

        if tf == "YTD":
            return f"{today.year}-01-01", today.isoformat()
        if tf == "1M":
            return (today - timedelta(days=30)).isoformat(), today.isoformat()
        if tf == "3M":
            return (today - timedelta(days=90)).isoformat(), today.isoformat()
        if tf == "6M":
            return (today - timedelta(days=180)).isoformat(), today.isoformat()
        if tf == "1Y":
            return (today - timedelta(days=365)).isoformat(), today.isoformat()

        # ALL or fallback
        return (start_date or "").strip(), (end_date or "").strip()

    async def get_performance_analytics(
        self,
        timeframe: str = "ALL",
        start_date: str | None = None,
        end_date: str | None = None,
        currency: str = "THB",
    ) -> PortfolioPerformanceResponse:
        resolved_start, resolved_end = self.resolve_date_range(timeframe, start_date, end_date)
        target_currency = currency.upper()
        cache_key = f"perf_{timeframe}_{resolved_start}_{resolved_end}_{target_currency}"
        cached = ttl_cache.get(cache_key)
        if cached is not None:
            return cast(PortfolioPerformanceResponse, cached)

        async def _do_calc_perf() -> PortfolioPerformanceResponse:
            c = ttl_cache.get(cache_key)
            if c is not None:
                return cast(PortfolioPerformanceResponse, c)

            holdings_res = await self.valuation_service.get_portfolio_holdings(tab_id="all", currency=target_currency)
            if holdings_res.error:
                return PortfolioPerformanceResponse(
                    timeframe=timeframe,
                    startDate=resolved_start,
                    endDate=resolved_end,
                    currency=target_currency,
                    exchangeRate=holdings_res.exchangeRate,
                    summary=holdings_res.summary,
                    assetTypePerformance=[],
                    topGainers=[],
                    topLosers=[],
                    symbolPerformance=[],
                    error=holdings_res.error,
                )

            res = self.calculate_performance(
                holdings_res=holdings_res,
                timeframe=timeframe,
                start_date=resolved_start,
                end_date=resolved_end,
            )
            if not res.error:
                ttl_cache.set(cache_key, res, ttl=60.0)
            return res

        return await singleflight.execute(cache_key, _do_calc_perf)

    def calculate_performance(
        self,
        holdings_res,
        timeframe: str,
        start_date: str = "",
        end_date: str = "",
    ) -> PortfolioPerformanceResponse:
        type_map: dict[str, dict] = {}
        symbol_map: dict[str, dict] = {}

        open_invested_total = 0.0
        open_value_total = 0.0
        closed_invested_total = 0.0
        closed_realized_total = 0.0

        # 1. Process Open Positions
        for pos in holdings_res.openPositions:
            asset_type = pos.assetType
            sym = pos.symbol

            open_invested_total += pos.totalCost
            open_value_total += pos.holdingValue

            # Type Map
            if asset_type not in type_map:
                type_map[asset_type] = {
                    "type": asset_type,
                    "investedCost": 0.0,
                    "currentValue": 0.0,
                    "realizedPL": 0.0,
                    "unrealizedPL": 0.0,
                    "openSymbolCount": 0,
                    "closedSymbolCount": 0,
                }
            t = type_map[asset_type]
            t["investedCost"] += pos.totalCost
            t["currentValue"] += pos.holdingValue
            t["unrealizedPL"] += pos.unrealizedPL
            t["openSymbolCount"] += 1

            # Symbol Map
            symbol_map[sym] = {
                "symbol": sym,
                "displaySymbol": pos.displaySymbol,
                "name": pos.name,
                "assetType": asset_type,
                "assetTypeLabel": pos.assetTypeLabel,
                "status": "OPEN",
                "investedCost": pos.totalCost,
                "currentValue": pos.holdingValue,
                "realizedPL": 0.0,
                "unrealizedPL": pos.unrealizedPL,
                "hasPrice": pos.hasPrice,
            }

        # 2. Process Closed Positions with Date Range Filtering
        for closed in holdings_res.closedPositions:
            asset_type = closed.assetType
            sym = closed.symbol

            if asset_type not in type_map:
                type_map[asset_type] = {
                    "type": asset_type,
                    "investedCost": 0.0,
                    "currentValue": 0.0,
                    "realizedPL": 0.0,
                    "unrealizedPL": 0.0,
                    "openSymbolCount": 0,
                    "closedSymbolCount": 0,
                }
            type_map[asset_type]["closedSymbolCount"] += 1

            closed_invested = 0.0
            closed_proceeds = 0.0
            realized_pl = 0.0

            for lot in closed.lots:
                in_range = True
                if start_date and end_date:
                    in_range = start_date <= lot.closeDate <= end_date

                if in_range:
                    closed_invested += lot.totalCost
                    closed_proceeds += lot.totalProceeds or (lot.totalCost + lot.realizedPL)
                    realized_pl += lot.realizedPL

            closed_invested_total += closed_invested
            closed_realized_total += realized_pl

            type_map[asset_type]["investedCost"] += closed_invested
            type_map[asset_type]["realizedPL"] += realized_pl

            if sym in symbol_map:
                existing = symbol_map[sym]
                existing["status"] = "BOTH"
                existing["investedCost"] += closed_invested
                existing["currentValue"] += closed_proceeds
                existing["realizedPL"] += realized_pl
            else:
                symbol_map[sym] = {
                    "symbol": sym,
                    "displaySymbol": closed.displaySymbol,
                    "name": closed.name,
                    "assetType": asset_type,
                    "assetTypeLabel": closed.assetTypeLabel,
                    "status": "CLOSED",
                    "investedCost": closed_invested,
                    "currentValue": closed_proceeds,
                    "realizedPL": realized_pl,
                    "unrealizedPL": 0.0,
                    "hasPrice": False,
                }

        # 3. Assemble Asset Class Performance
        asset_type_performance: list[AssetClassPerformance] = []
        for t in type_map.values():
            tot_return = t["realizedPL"] + t["unrealizedPL"]
            tot_return_pct = (tot_return / t["investedCost"] * 100.0) if t["investedCost"] > 0 else 0.0
            asset_type_performance.append(
                AssetClassPerformance(
                    assetType=t["type"],
                    label=get_asset_type_label(t["type"]),
                    investedCost=t["investedCost"],
                    currentValue=t["currentValue"],
                    unrealizedPL=t["unrealizedPL"],
                    realizedPL=t["realizedPL"],
                    totalReturn=tot_return,
                    totalReturnPercent=tot_return_pct,
                    openSymbolCount=t["openSymbolCount"],
                    closedSymbolCount=t["closedSymbolCount"],
                )
            )
        asset_type_performance.sort(key=lambda x: x.totalReturnPercent, reverse=True)

        # 4. Assemble Symbol Performance
        symbol_performance: list[SymbolPerformance] = []
        for s in symbol_map.values():
            tot_return = s["realizedPL"] + s["unrealizedPL"]
            tot_return_pct = (tot_return / s["investedCost"] * 100.0) if s["investedCost"] > 0 else 0.0
            symbol_performance.append(
                SymbolPerformance(
                    symbol=s["symbol"],
                    displaySymbol=s["displaySymbol"],
                    name=s["name"],
                    assetType=s["assetType"],
                    assetTypeLabel=s["assetTypeLabel"],
                    status=s["status"],
                    investedCost=s["investedCost"],
                    currentValue=s["currentValue"],
                    unrealizedPL=s["unrealizedPL"],
                    realizedPL=s["realizedPL"],
                    totalReturnAmount=tot_return,
                    totalReturn=tot_return,
                    totalReturnPercent=tot_return_pct,
                    hasPrice=s["hasPrice"],
                )
            )

        # Sort: default by totalReturnPercent descending
        symbol_performance.sort(key=lambda x: x.totalReturnPercent, reverse=True)

        # 5. Top Gainers & Losers
        top_gainers = [s for s in symbol_performance if s.totalReturnPercent > 0][:5]
        top_losers = sorted(
            [s for s in symbol_performance if s.totalReturnPercent < 0], key=lambda x: x.totalReturnPercent
        )[:5]

        # 6. Overall Portfolio Summary with Date-Filtered Realized PL
        total_unrealized_pl = open_value_total - open_invested_total
        total_unrealized_pl_pct = (
            (total_unrealized_pl / open_invested_total * 100.0) if open_invested_total > 0 else 0.0
        )
        total_realized_pl_pct = (
            (closed_realized_total / closed_invested_total * 100.0) if closed_invested_total > 0 else 0.0
        )
        total_invested = open_invested_total + closed_invested_total
        total_return = total_unrealized_pl + closed_realized_total
        total_return_pct = (total_return / total_invested * 100.0) if total_invested > 0 else 0.0

        summary = PortfolioSummary(
            totalInvested=total_invested,
            totalValue=open_value_total,
            openInvested=open_invested_total,
            closedInvested=closed_invested_total,
            totalUnrealizedPL=total_unrealized_pl,
            totalUnrealizedPLPercent=total_unrealized_pl_pct,
            totalRealizedPL=closed_realized_total,
            totalRealizedPLPercent=total_realized_pl_pct,
            totalReturn=total_return,
            totalReturnPercent=total_return_pct,
        )

        return PortfolioPerformanceResponse(
            timeframe=timeframe,
            startDate=start_date,
            endDate=end_date,
            currency=holdings_res.currency,
            exchangeRate=holdings_res.exchangeRate,
            summary=summary,
            assetTypePerformance=asset_type_performance,
            topGainers=top_gainers,
            topLosers=top_losers,
            symbolPerformance=symbol_performance,
            error=None,
        )
