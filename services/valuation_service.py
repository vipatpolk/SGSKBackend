from typing import Any, cast

import httpx

from models.portfolio import (
    ClosedPortfolioPosition,
    PortfolioHoldingLot,
    PortfolioHoldingsResponse,
    PortfolioPosition,
    PortfolioSummary,
)
from models.transaction import ClosedShareLot, PriceData, SheetResult
from services.nav_service import NavService
from services.price_service import PriceService
from services.share_lot_service import ShareLotService
from utils.cache import singleflight, ttl_cache
from utils.format_utils import (
    convert_currency,
    display_symbol,
    get_asset_type,
    get_asset_type_label,
)

DEFAULT_PVD_NAMES: dict[str, str] = {
    "PVDSP500": "นโยบายกองทุนรวมต่างประเทศ หุ้นยูเอส",
    "PVDWEQ": "นโยบายกองทุนรวมต่างประเทศ World Equity",
    "PVDMPAEM": "นโยบายกองทุนรวมตราสารทุน เอเชียน อีเมอร์จิ้ง",
    "PVDMPINC": "นโยบายกองทุนรวมตราสารหนี้ต่างประเทศ อินคัม",
    "PVDMGLDH": "นโยบายกองทุนรวมโกลด์ THB เฮดจ์",
}


class ValuationService:
    def __init__(
        self,
        share_lot_service: ShareLotService | None = None,
        price_service: PriceService | None = None,
        nav_service: NavService | None = None,
        client: httpx.AsyncClient | None = None,
    ):
        self.share_lot_service = share_lot_service or ShareLotService(client=client)
        self.price_service = price_service or PriceService(client=client)
        self.nav_service = nav_service or (
            self.price_service.nav_service if self.price_service else NavService(client=client)
        )

    async def get_portfolio_holdings(
        self,
        tab_id: str = "all",
        currency: str = "THB",
    ) -> PortfolioHoldingsResponse:
        target_currency = currency.upper()
        cache_key = f"valuation_{tab_id}_{target_currency}"
        cached = ttl_cache.get(cache_key)
        if cached is not None:
            return cast(PortfolioHoldingsResponse, cached)

        base_cache_key = f"valuation_base_{tab_id}"
        base_cached = ttl_cache.get(base_cache_key)

        sheet_result: SheetResult
        price_data_map: dict[str, Any]
        exchange_rate: float

        if base_cached is not None:
            sheet_result, price_data_map, exchange_rate = base_cached
        else:
            async def _resolve_base() -> tuple[SheetResult, dict[str, Any], float]:
                c = ttl_cache.get(base_cache_key)
                if c is not None:
                    return cast(tuple[SheetResult, dict[str, Any], float], c)

                is_all = tab_id == "all"
                if is_all:
                    s_res = await self.share_lot_service.fetch_all_sheets()
                else:
                    s_res = await self.share_lot_service.fetch_sheet(tab_id)

                if s_res.error:
                    return s_res, {}, 1.0

                # Extract symbols for price resolution
                candidates: list[dict[str, str]] = []
                seen = set()
                for o_item in s_res.summaries or []:
                    if o_item.symbol and o_item.symbol not in seen:
                        seen.add(o_item.symbol)
                        candidates.append({"symbol": o_item.symbol, "assetType": o_item.assetType})
                for c_item in s_res.closedSummaries or []:
                    if c_item.symbol and c_item.symbol not in seen:
                        seen.add(c_item.symbol)
                        candidates.append({"symbol": c_item.symbol, "assetType": c_item.assetType})
                for t_item in s_res.transactionSummaries or []:
                    if t_item.symbol and t_item.symbol not in seen:
                        seen.add(t_item.symbol)
                        candidates.append({"symbol": t_item.symbol, "assetType": t_item.assetType})

                p_map: dict[str, Any] = {}
                ex_rate: float = 1.0
                if candidates:
                    market_res = await self.price_service.fetch_prices_and_rate(candidates)
                    p_map = market_res.get("prices", {})
                    ex_rate = float(market_res.get("rate", 1.0) or 1.0)
                else:
                    ex_rate = await self.price_service.fetch_exchange_rate("USD", "THB") or 1.0

                has_pvd = any(
                    c.get("assetType") == "provident-fund" or c.get("symbol", "").upper().startswith("PVD")
                    for c in candidates
                )
                if has_pvd:
                    try:
                        pvd_policies = await self.nav_service.fetch_pvd_policies()
                        for sym_key, policy_info in pvd_policies.items():
                            sec_name = policy_info.get("name") or DEFAULT_PVD_NAMES.get(sym_key, "")
                            if sym_key not in p_map:
                                p_map[sym_key] = PriceData(symbol=sym_key, name=sec_name, price=0.0, currency="THB")
                            elif not p_map[sym_key].name:
                                p_map[sym_key].name = sec_name
                    except Exception:
                        pass

                base_val = (s_res, p_map, ex_rate)
                ttl_cache.set(base_cache_key, base_val, ttl=60.0)
                return base_val

            sheet_result, price_data_map, exchange_rate = await singleflight.execute(
                f"resolve_base_{tab_id}", _resolve_base
            )

        if sheet_result.error:
            return self._create_empty_response(tab_id, target_currency, sheet_result.error)

        res = self.value_sheet_result(
            sheet_result=sheet_result,
            price_data_map=price_data_map,
            exchange_rate=exchange_rate,
            target_currency=target_currency,
            tab_id=tab_id,
        )
        if not res.error:
            ttl_cache.set(cache_key, res, ttl=60.0)
        return res

    def value_sheet_result(
        self,
        sheet_result: SheetResult,
        price_data_map: dict[str, Any],
        exchange_rate: float,
        target_currency: str = "THB",
        tab_id: str = "all",
    ) -> PortfolioHoldingsResponse:
        open_positions: list[PortfolioPosition] = []
        closed_positions: list[ClosedPortfolioPosition] = []

        open_invested_total = 0.0
        open_value_total = 0.0
        closed_invested_total = 0.0
        closed_realized_total = 0.0

        # 1. Open Positions
        for open_summary in sheet_result.summaries or []:
            sym = open_summary.symbol
            orig_curr = open_summary.currency
            pd = price_data_map.get(sym)
            is_pvd = open_summary.assetType == "provident-fund" or sym.upper().startswith("PVD")

            has_price = bool(pd is not None and getattr(pd, "price", 0.0) > 0)
            pvd_total_val = 0.0
            if is_pvd:
                has_price = True
                price_curr = orig_curr
                emp_val = (open_summary.employeeContribution or 0.0) + (open_summary.employeeEarnings or 0.0)
                empr_val = (open_summary.employerMatching or 0.0) + (open_summary.employerEarnings or 0.0)
                pvd_total_val = emp_val + empr_val
                if pvd_total_val <= 0:
                    pvd_total_val = open_summary.totalCost
                raw_price = (
                    (pvd_total_val / open_summary.totalShares)
                    if open_summary.totalShares > 0
                    else open_summary.averageCost
                )
            else:
                raw_price = pd.price if (has_price and pd is not None) else open_summary.averageCost
                price_curr = pd.currency if (has_price and pd is not None and pd.currency) else orig_curr

            # Price converted to target currency
            current_price_converted = convert_currency(raw_price, price_curr, target_currency, exchange_rate)
            # Total cost converted to target currency
            total_cost_converted = convert_currency(open_summary.totalCost, orig_curr, target_currency, exchange_rate)
            average_cost_converted = (
                total_cost_converted / open_summary.totalShares if open_summary.totalShares > 0 else 0.0
            )

            # Holding value
            if is_pvd:
                holding_value_converted = convert_currency(pvd_total_val, orig_curr, target_currency, exchange_rate)
                unrealized_pl = holding_value_converted - total_cost_converted
                unrealized_pl_pct = (
                    (unrealized_pl / total_cost_converted * 100.0) if total_cost_converted > 0 else 0.0
                )
            else:
                holding_value_converted = open_summary.totalShares * current_price_converted
                unrealized_pl = holding_value_converted - total_cost_converted
                unrealized_pl_pct = (
                    (unrealized_pl / total_cost_converted * 100.0) if total_cost_converted > 0 else 0.0
                )

            open_invested_total += total_cost_converted
            open_value_total += holding_value_converted

            # Lot-level valuations
            valued_lots: list[PortfolioHoldingLot] = []
            for lot in open_summary.lots:
                lot_cost_converted = convert_currency(lot.totalCost, orig_curr, target_currency, exchange_rate)
                lot_cost_basis_converted = lot_cost_converted / lot.quantity if lot.quantity > 0 else 0.0
                lot_holding_value = lot.quantity * current_price_converted
                lot_unrealized_pl = lot_holding_value - lot_cost_converted
                lot_unrealized_pl_pct = (
                    (lot_unrealized_pl / lot_cost_converted * 100.0) if lot_cost_converted > 0 else 0.0
                )

                valued_lots.append(
                    PortfolioHoldingLot(
                        purchaseDate=lot.purchaseDate,
                        quantity=lot.quantity,
                        costBasis=lot_cost_basis_converted,
                        totalCost=lot_cost_converted,
                        currentPrice=current_price_converted,
                        holdingValue=lot_holding_value,
                        unrealizedPL=lot_unrealized_pl,
                        unrealizedPLPercent=lot_unrealized_pl_pct,
                        assetType=lot.assetType,
                        currency=target_currency,
                        originalCostBasis=lot.costBasis,
                        originalCurrency=orig_curr,
                        note=lot.note,
                    )
                )

            name = pd.name if (pd is not None and pd.name) else ""
            if not name and is_pvd:
                name = DEFAULT_PVD_NAMES.get(sym.upper(), "")

            emp_contrib_c = (
                convert_currency(open_summary.employeeContribution, orig_curr, target_currency, exchange_rate)
                if open_summary.employeeContribution is not None
                else None
            )
            emp_earnings_c = (
                convert_currency(open_summary.employeeEarnings, orig_curr, target_currency, exchange_rate)
                if open_summary.employeeEarnings is not None
                else None
            )
            empr_matching_c = (
                convert_currency(open_summary.employerMatching, orig_curr, target_currency, exchange_rate)
                if open_summary.employerMatching is not None
                else None
            )
            empr_earnings_c = (
                convert_currency(open_summary.employerEarnings, orig_curr, target_currency, exchange_rate)
                if open_summary.employerEarnings is not None
                else None
            )

            open_positions.append(
                PortfolioPosition(
                    symbol=sym,
                    displaySymbol=display_symbol(sym),
                    name=name,
                    assetType=get_asset_type(open_summary.assetType, sym),
                    assetTypeLabel=get_asset_type_label(open_summary.assetType, sym),
                    totalShares=open_summary.totalShares,
                    totalCost=total_cost_converted,
                    averageCost=average_cost_converted,
                    currentPrice=current_price_converted,
                    holdingValue=holding_value_converted,
                    unrealizedPL=unrealized_pl,
                    unrealizedPLPercent=unrealized_pl_pct,
                    currency=target_currency,
                    originalCurrency=orig_curr,
                    hasPrice=has_price,
                    lots=valued_lots,
                    employeeShares=open_summary.employeeShares,
                    employerShares=open_summary.employerShares,
                    employeeContribution=emp_contrib_c,
                    employeeEarnings=emp_earnings_c,
                    employerMatching=empr_matching_c,
                    employerEarnings=empr_earnings_c,
                )
            )

        # 2. Closed Positions
        for closed_summary in sheet_result.closedSummaries or []:
            sym = closed_summary.symbol
            orig_curr = closed_summary.currency
            pd = price_data_map.get(sym)

            cost_converted = convert_currency(closed_summary.totalCost, orig_curr, target_currency, exchange_rate)
            proceeds_converted = convert_currency(
                closed_summary.totalProceeds, orig_curr, target_currency, exchange_rate
            )
            realized_pl_converted = convert_currency(
                closed_summary.realizedPL, orig_curr, target_currency, exchange_rate
            )
            realized_pl_pct = (realized_pl_converted / cost_converted * 100.0) if cost_converted > 0 else 0.0

            avg_buy_converted = cost_converted / closed_summary.closedShares if closed_summary.closedShares > 0 else 0.0
            avg_sell_converted = (
                proceeds_converted / closed_summary.closedShares if closed_summary.closedShares > 0 else 0.0
            )

            closed_invested_total += cost_converted
            closed_realized_total += realized_pl_converted

            # Closed lots converted
            valued_closed_lots: list[ClosedShareLot] = []
            for c_lot in closed_summary.lots:
                lot_curr = c_lot.currency or orig_curr
                lot_cost = convert_currency(c_lot.totalCost, lot_curr, target_currency, exchange_rate)
                lot_proceeds = convert_currency(c_lot.totalProceeds, lot_curr, target_currency, exchange_rate)
                lot_pl = convert_currency(c_lot.realizedPL, lot_curr, target_currency, exchange_rate)
                lot_pl_pct = (lot_pl / lot_cost * 100.0) if lot_cost > 0 else 0.0
                lot_basis = lot_cost / c_lot.quantity if c_lot.quantity > 0 else 0.0
                lot_sell = lot_proceeds / c_lot.quantity if c_lot.quantity > 0 else 0.0

                valued_closed_lots.append(
                    ClosedShareLot(
                        symbol=c_lot.symbol,
                        purchaseDate=c_lot.purchaseDate,
                        closeDate=c_lot.closeDate,
                        quantity=c_lot.quantity,
                        costBasis=lot_basis,
                        sellPrice=lot_sell,
                        totalCost=lot_cost,
                        totalProceeds=lot_proceeds,
                        realizedPL=lot_pl,
                        realizedPLPercent=lot_pl_pct,
                        currency=target_currency,
                        assetType=c_lot.assetType,
                    )
                )

            name = pd.name if (pd is not None and pd.name) else ""

            closed_positions.append(
                ClosedPortfolioPosition(
                    symbol=sym,
                    displaySymbol=display_symbol(sym),
                    name=name,
                    assetType=get_asset_type(closed_summary.assetType, sym),
                    assetTypeLabel=get_asset_type_label(closed_summary.assetType, sym),
                    totalShares=0.0,
                    closedShares=closed_summary.closedShares,
                    totalCost=cost_converted,
                    totalProceeds=proceeds_converted,
                    realizedPL=realized_pl_converted,
                    realizedPLPercent=realized_pl_pct,
                    averageBuyPrice=avg_buy_converted,
                    averageSellPrice=avg_sell_converted,
                    currency=target_currency,
                    originalCurrency=orig_curr,
                    lots=valued_closed_lots,
                )
            )

        # 3. High-level Summary KPIs
        total_unrealized_pl = open_value_total - open_invested_total
        total_unrealized_pl_pct = (
            (total_unrealized_pl / open_invested_total * 100.0) if open_invested_total > 0 else 0.0
        )
        total_realized_pl_pct = (
            (closed_realized_total / closed_invested_total * 100.0) if closed_invested_total > 0 else 0.0
        )
        total_invested = open_invested_total + closed_invested_total
        total_return = closed_realized_total + total_unrealized_pl
        total_return_pct = (total_return / total_invested * 100.0) if total_invested > 0 else 0.0

        portfolio_summary = PortfolioSummary(
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

        return PortfolioHoldingsResponse(
            currency=target_currency,
            exchangeRate=exchange_rate,
            tabId=tab_id,
            summary=portfolio_summary,
            openPositions=open_positions,
            closedPositions=closed_positions,
            transactionSummaries=sheet_result.transactionSummaries,
            rawTransactions=sheet_result.rawTransactions,
            error=None,
        )

    def _create_empty_response(self, tab_id: str, currency: str, error: str) -> PortfolioHoldingsResponse:
        return PortfolioHoldingsResponse(
            currency=currency,
            exchangeRate=1.0,
            tabId=tab_id,
            summary=PortfolioSummary(
                totalInvested=0.0,
                totalValue=0.0,
                openInvested=0.0,
                closedInvested=0.0,
                totalUnrealizedPL=0.0,
                totalUnrealizedPLPercent=0.0,
                totalRealizedPL=0.0,
                totalRealizedPLPercent=0.0,
                totalReturn=0.0,
                totalReturnPercent=0.0,
            ),
            openPositions=[],
            closedPositions=[],
            transactionSummaries=[],
            rawTransactions=[],
            error=error,
        )
