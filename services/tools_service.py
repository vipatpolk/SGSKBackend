import logging
import math

from models.tools import (
    AssetClassRebalanceGroupModel,
    CompoundingFrequency,
    PositionSnapshotModel,
    RebalanceAction,
    RebalanceCalculateRequest,
    RebalanceCalculateResponse,
    RebalanceTradeOrderModel,
    SimulateOrderRequest,
    SimulateOrderResponse,
    SimulationDeltaMetrics,
    SimulationStateMetrics,
    SolveTargetCostRequest,
    SolveTargetCostResponse,
    SymbolRebalanceItemModel,
    TvmCalculateRequest,
    TvmCalculateResponse,
    TvmScheduleEntryModel,
)
from services.allocation_service import DEFAULT_TARGETS
from services.valuation_service import ValuationService

logger = logging.getLogger(__name__)

COMPOUNDING_PERIODS: dict[CompoundingFrequency, int] = {
    "daily": 365,
    "weekly": 52,
    "biweekly": 26,
    "semimonthly": 24,
    "monthly": 12,
    "quarterly": 4,
    "semiannually": 2,
    "annually": 1,
}


class ToolsService:
    def __init__(self, valuation_service: ValuationService | None = None) -> None:
        self.valuation_service = valuation_service or ValuationService()

    async def simulate_order(self, req: SimulateOrderRequest) -> SimulateOrderResponse:
        initial = await self._resolve_initial_position(req.initialPosition, req.symbol, req.currency)

        init_shares = float(initial.shares)
        init_total_cost = float(initial.totalCost if initial.totalCost is not None else (init_shares * initial.avgCost))
        init_avg_cost = (init_total_cost / init_shares) if init_shares > 0 else 0.0
        market_price = float(initial.marketPrice)
        init_holding_val = init_shares * market_price
        init_unrealized_pl = init_holding_val - init_total_cost
        init_unrealized_pl_pct = (init_unrealized_pl / init_total_cost * 100.0) if init_total_cost > 0 else 0.0

        sim_shares = init_shares
        sim_total_cost = init_total_cost
        sim_avg_cost = init_avg_cost
        sim_realized_pl = 0.0
        total_outlay = 0.0
        total_proceeds = 0.0
        total_fees = 0.0

        for step in req.steps:
            shares = float(step.shares)
            price = float(step.price)
            fee_pct = float(step.feePercent or req.taxFeePercent or 0.0)

            if step.action == "BUY":
                fee = shares * price * (fee_pct / 100.0)
                step_cost = (shares * price) + fee
                sim_shares += shares
                sim_total_cost += step_cost
                sim_avg_cost = (sim_total_cost / sim_shares) if sim_shares > 0 else 0.0
                total_outlay += step_cost
                total_fees += fee

            elif step.action == "SELL":
                if sim_shares <= 0:
                    continue
                actual_sell_shares = min(shares, sim_shares)
                gross = actual_sell_shares * price
                fee = gross * (fee_pct / 100.0)
                net = gross - fee
                cost_sold = actual_sell_shares * sim_avg_cost
                step_realized_pl = net - cost_sold

                sim_realized_pl += step_realized_pl
                sim_shares -= actual_sell_shares
                sim_total_cost -= cost_sold

                if sim_shares <= 0:
                    sim_shares = 0.0
                    sim_total_cost = 0.0
                    sim_avg_cost = 0.0
                else:
                    sim_avg_cost = sim_total_cost / sim_shares

                total_proceeds += net
                total_fees += fee

        sim_holding_val = sim_shares * market_price
        sim_unrealized_pl = sim_holding_val - sim_total_cost
        sim_unrealized_pl_pct = (sim_unrealized_pl / sim_total_cost * 100.0) if sim_total_cost > 0 else 0.0

        delta_shares = sim_shares - init_shares
        delta_shares_pct = (delta_shares / init_shares * 100.0) if init_shares > 0 else 0.0
        delta_avg_cost = sim_avg_cost - init_avg_cost
        delta_avg_cost_pct = (delta_avg_cost / init_avg_cost * 100.0) if init_avg_cost > 0 else 0.0
        delta_total_cost = sim_total_cost - init_total_cost
        delta_total_cost_pct = (delta_total_cost / init_total_cost * 100.0) if init_total_cost > 0 else 0.0
        delta_holding_val = sim_holding_val - init_holding_val
        delta_holding_val_pct = (delta_holding_val / init_holding_val * 100.0) if init_holding_val > 0 else 0.0
        delta_unrealized_pl = sim_unrealized_pl - init_unrealized_pl
        delta_unrealized_pl_pct = sim_unrealized_pl_pct - init_unrealized_pl_pct

        breakeven_dist_init = ((init_avg_cost - market_price) / market_price * 100.0) if market_price > 0 else 0.0
        breakeven_dist_sim = ((sim_avg_cost - market_price) / market_price * 100.0) if market_price > 0 else 0.0

        return SimulateOrderResponse(
            initial=SimulationStateMetrics(
                totalShares=round(init_shares, 6),
                averageCost=round(init_avg_cost, 4),
                totalCost=round(init_total_cost, 2),
                marketPrice=round(market_price, 4),
                holdingValue=round(init_holding_val, 2),
                unrealizedPL=round(init_unrealized_pl, 2),
                unrealizedPLPercent=round(init_unrealized_pl_pct, 2),
                realizedPL=0.0,
            ),
            simulated=SimulationStateMetrics(
                totalShares=round(sim_shares, 6),
                averageCost=round(sim_avg_cost, 4),
                totalCost=round(sim_total_cost, 2),
                marketPrice=round(market_price, 4),
                holdingValue=round(sim_holding_val, 2),
                unrealizedPL=round(sim_unrealized_pl, 2),
                unrealizedPLPercent=round(sim_unrealized_pl_pct, 2),
                realizedPL=round(sim_realized_pl, 2),
            ),
            delta=SimulationDeltaMetrics(
                shares=round(delta_shares, 6),
                sharesPercent=round(delta_shares_pct, 2),
                averageCost=round(delta_avg_cost, 4),
                averageCostPercent=round(delta_avg_cost_pct, 2),
                totalCost=round(delta_total_cost, 2),
                totalCostPercent=round(delta_total_cost_pct, 2),
                holdingValue=round(delta_holding_val, 2),
                holdingValuePercent=round(delta_holding_val_pct, 2),
                unrealizedPL=round(delta_unrealized_pl, 2),
                unrealizedPLPercent=round(delta_unrealized_pl_pct, 2),
                breakevenDistanceInitial=round(breakeven_dist_init, 2),
                breakevenDistanceSimulated=round(breakeven_dist_sim, 2),
                realizedPL=round(sim_realized_pl, 2),
            ),
            steps=req.steps,
            totalCapitalOutlay=round(total_outlay, 2),
            totalProceeds=round(total_proceeds, 2),
            totalFees=round(total_fees, 2),
            currency=initial.currency,
        )

    async def solve_target_cost(self, req: SolveTargetCostRequest) -> SolveTargetCostResponse:
        initial = await self._resolve_initial_position(req.initialPosition, req.symbol, req.currency)

        s0 = float(initial.shares)
        c0 = float(initial.totalCost if initial.totalCost is not None else (s0 * initial.avgCost))
        p0 = float(initial.avgCost) if s0 > 0 else 0.0
        target = float(req.targetAvgCost)
        p_buy = float(req.purchasePrice)
        fee_pct = float(req.feePercent or 0.0)
        f = fee_pct / 100.0
        p_eff = p_buy * (1.0 + f)

        if s0 <= 0:
            if p_eff <= 0:
                return SolveTargetCostResponse(
                    isValid=False,
                    errorMessage="Purchase price must be greater than zero.",
                    currency=initial.currency,
                )
            req_shares = 1.0
            req_capital = req_shares * p_buy
            fee_amount = req_capital * f
            total_outlay = req_capital + fee_amount
            return SolveTargetCostResponse(
                isValid=True,
                requiredShares=round(req_shares, 6),
                requiredCapital=round(req_capital, 2),
                feeAmount=round(fee_amount, 2),
                totalOutlay=round(total_outlay, 2),
                achievedAvgCost=round(total_outlay / req_shares, 4),
                newTotalShares=round(req_shares, 6),
                newTotalCost=round(total_outlay, 2),
                currency=initial.currency,
            )

        denom = target - p_eff
        if abs(denom) < 1e-9:
            return SolveTargetCostResponse(
                isValid=False,
                errorMessage="Target average cost equals effective buy price. Mathematical boundary.",
                currency=initial.currency,
            )

        req_shares = (c0 - (s0 * target)) / denom

        if req_shares <= 0:
            if p_eff >= target and target < p0:
                msg = (
                    f"Cannot average down to {target:.2f} when effective buy price ({p_eff:.2f}) "
                    f"is higher than or equal to target cost."
                )
            elif p_eff <= target and target > p0:
                msg = (
                    f"Cannot average up to {target:.2f} when effective buy price ({p_eff:.2f}) "
                    f"is lower than or equal to target cost."
                )
            else:
                msg = "No additional shares required or target is already achieved."

            return SolveTargetCostResponse(
                isValid=False,
                errorMessage=msg,
                currency=initial.currency,
            )

        req_capital = req_shares * p_buy
        fee_amount = req_capital * f
        total_outlay = req_capital + fee_amount
        new_shares = s0 + req_shares
        new_cost = c0 + total_outlay
        achieved_cost = new_cost / new_shares if new_shares > 0 else 0.0

        return SolveTargetCostResponse(
            isValid=True,
            requiredShares=round(req_shares, 6),
            requiredCapital=round(req_capital, 2),
            feeAmount=round(fee_amount, 2),
            totalOutlay=round(total_outlay, 2),
            achievedAvgCost=round(achieved_cost, 4),
            newTotalShares=round(new_shares, 6),
            newTotalCost=round(new_cost, 2),
            currency=initial.currency,
        )

    async def _resolve_initial_position(
        self,
        snapshot: PositionSnapshotModel | None,
        symbol: str | None,
        currency: str,
    ) -> PositionSnapshotModel:
        if snapshot is not None and (snapshot.shares > 0 or snapshot.avgCost > 0):
            return snapshot

        lookup_symbol = (symbol or (snapshot.symbol if snapshot else "") or "").upper()
        if not lookup_symbol:
            return snapshot or PositionSnapshotModel(currency=currency)

        try:
            holdings = await self.valuation_service.get_portfolio_holdings(tab_id="all", currency=currency)
            for pos in holdings.openPositions:
                if pos.symbol.upper() == lookup_symbol:
                    return PositionSnapshotModel(
                        symbol=pos.symbol,
                        shares=pos.totalShares,
                        avgCost=pos.averageCost,
                        marketPrice=pos.currentPrice,
                        currency=pos.currency,
                        totalCost=pos.totalCost,
                    )
        except Exception as err:
            logger.warning(f"Failed to auto-resolve position for {lookup_symbol}: {err}")

        return snapshot or PositionSnapshotModel(symbol=lookup_symbol, currency=currency)

    async def calculate_tvm(self, req: TvmCalculateRequest) -> TvmCalculateResponse:
        m = COMPOUNDING_PERIODS.get(req.compounding, 12)
        pv = max(0.0, float(req.presentValue))
        pmt = max(0.0, float(req.payment))
        rate_pct = max(0.0, float(req.annualRatePct))
        years = max(0.0, float(req.years))
        fv = max(0.0, float(req.targetFutureValue or 0.0))
        t = 1.0 if req.timing == "beginning" else 0.0

        is_valid = True
        error_message = ""

        if req.mode == "FV":
            fv = self._tvm_future_value(pv, pmt, rate_pct, years, m, t)
        elif req.mode == "PMT":
            if years <= 0:
                is_valid = False
                error_message = "Investment horizon must be greater than 0 years to calculate payment."
                pmt = 0.0
            else:
                pmt = self._tvm_payment(fv, pv, rate_pct, years, m, t)
        elif req.mode == "PV":
            if years <= 0:
                pv = fv
            else:
                pv = self._tvm_present_value(fv, pmt, rate_pct, years, m, t)
        elif req.mode == "N":
            res_years, is_valid, error_message = self._tvm_years(fv, pv, pmt, rate_pct, m, t)
            years = res_years
        elif req.mode == "RATE":
            if years <= 0:
                is_valid = False
                error_message = "Investment horizon must be greater than 0 years to calculate return rate."
                rate_pct = 0.0
            else:
                res_rate, is_valid, error_message = self._tvm_rate(fv, pv, pmt, years, m, t)
                rate_pct = res_rate

        total_periods = int(math.ceil(years * m))
        total_principal = pv
        total_contributions = pmt * total_periods
        total_invested = total_principal + total_contributions
        total_interest = max(0.0, fv - total_invested)

        periodic_rate = (rate_pct / 100.0) / m
        ear_pct = ((math.pow(1.0 + periodic_rate, m) - 1.0) * 100.0) if m > 0 else rate_pct
        multiplier = (fv / total_invested) if total_invested > 0 else (1.0 if fv > 0 else 0.0)

        schedule: list[TvmScheduleEntryModel] = []
        if is_valid and years > 0:
            schedule = self._tvm_generate_schedule(pv, pmt, rate_pct, years, m, t)

        return TvmCalculateResponse(
            mode=req.mode,
            futureValue=round(fv, 2),
            presentValue=round(pv, 2),
            payment=round(pmt, 2),
            annualRatePct=round(rate_pct, 4),
            years=round(years, 2),
            compounding=req.compounding,
            compoundingPeriodsPerYear=m,
            totalPeriods=total_periods,
            totalPrincipal=round(total_principal, 2),
            totalContributions=round(total_contributions, 2),
            totalInvested=round(total_invested, 2),
            totalInterestEarned=round(total_interest, 2),
            effectiveAnnualRatePct=round(ear_pct, 4),
            multiplier=round(multiplier, 2),
            currency=req.currency,
            schedule=schedule,
            isValid=is_valid,
            errorMessage=error_message,
        )

    def _tvm_future_value(self, pv: float, pmt: float, rate_pct: float, years: float, m: int, t: float) -> float:
        n = years * m
        if n <= 0:
            return pv
        i = (rate_pct / 100.0) / m
        if abs(i) < 1e-12:
            return pv + pmt * n
        growth = math.pow(1.0 + i, n)
        fv_pv = pv * growth
        fv_pmt = pmt * ((growth - 1.0) / i) * (1.0 + i * t)
        return max(0.0, fv_pv + fv_pmt)

    def _tvm_present_value(self, fv: float, pmt: float, rate_pct: float, years: float, m: int, t: float) -> float:
        n = years * m
        if n <= 0:
            return fv
        i = (rate_pct / 100.0) / m
        if abs(i) < 1e-12:
            return max(0.0, fv - pmt * n)
        growth = math.pow(1.0 + i, n)
        fv_pmt = pmt * ((growth - 1.0) / i) * (1.0 + i * t)
        return max(0.0, (fv - fv_pmt) / growth)

    def _tvm_payment(self, fv: float, pv: float, rate_pct: float, years: float, m: int, t: float) -> float:
        n = years * m
        if n <= 0:
            return 0.0
        i = (rate_pct / 100.0) / m
        if abs(i) < 1e-12:
            return max(0.0, (fv - pv) / n)
        growth = math.pow(1.0 + i, n)
        fv_pv = pv * growth
        annuity_factor = ((growth - 1.0) / i) * (1.0 + i * t)
        if abs(annuity_factor) < 1e-12:
            return 0.0
        return max(0.0, (fv - fv_pv) / annuity_factor)

    def _tvm_years(
        self, fv: float, pv: float, pmt: float, rate_pct: float, m: int, t: float
    ) -> tuple[float, bool, str]:
        if fv <= pv:
            return 0.0, True, ""
        i = (rate_pct / 100.0) / m
        if abs(i) < 1e-12:
            if pmt <= 0:
                return 0.0, False, "With 0% return rate and 0 payment, target future value cannot be reached."
            n = (fv - pv) / pmt
            return n / m, True, ""

        adj_pmt = pmt * (1.0 + i * t)
        if pmt <= 0:
            if pv <= 0:
                return 0.0, False, "Both starting principal and periodic payment are zero."
            n = math.log(fv / pv) / math.log(1.0 + i)
            return n / m, True, ""

        num = fv * i + adj_pmt
        den = pv * i + adj_pmt
        if den <= 0 or num / den <= 0:
            return 0.0, False, "Cannot solve for time horizon with given inputs."

        n = math.log(num / den) / math.log(1.0 + i)
        return n / m, True, ""

    def _tvm_rate(self, fv: float, pv: float, pmt: float, years: float, m: int, t: float) -> tuple[float, bool, str]:
        n = max(1.0, years * m)
        total_invested = pv + pmt * n
        if fv <= total_invested:
            if fv == total_invested:
                return 0.0, True, ""
            if fv <= 0:
                return 0.0, False, "Target Future Value must be greater than 0."

        def f(rate_i: float) -> float:
            if abs(rate_i) < 1e-12:
                return pv + pmt * n - fv
            growth = math.pow(1.0 + rate_i, n)
            return pv * growth + pmt * ((growth - 1.0) / rate_i) * (1.0 + rate_i * t) - fv

        # Bisection search
        low = -0.95 / m
        high = 5.0 / m
        f_low = f(low)
        f_high = f(high)

        if f_low * f_high > 0:
            return 0.0, False, "Could not find a feasible return rate within standard boundaries."

        for _ in range(100):
            mid = (low + high) / 2.0
            f_mid = f(mid)
            if abs(f_mid) < 1e-7 or (high - low) < 1e-9:
                return mid * m * 100.0, True, ""
            if f_low * f_mid < 0:
                high = mid
                f_high = f_mid
            else:
                low = mid
                f_low = f_mid

        return ((low + high) / 2.0) * m * 100.0, True, ""

    def _tvm_generate_schedule(
        self, pv: float, pmt: float, rate_pct: float, years: float, m: int, t: float
    ) -> list[TvmScheduleEntryModel]:
        total_years = min(100, max(1, int(math.ceil(years))))
        periodic_rate = (rate_pct / 100.0) / m

        schedule: list[TvmScheduleEntryModel] = []
        current_balance = max(0.0, pv)
        cum_contrib = pv
        cum_interest = 0.0

        for y in range(1, total_years + 1):
            start_balance = current_balance
            year_contrib = 0.0
            year_interest = 0.0

            for _ in range(m):
                if t == 1.0:
                    current_balance += pmt
                    year_contrib += pmt
                    interest = current_balance * periodic_rate
                    current_balance += interest
                    year_interest += interest
                else:
                    interest = current_balance * periodic_rate
                    current_balance += interest + pmt
                    year_contrib += pmt
                    year_interest += interest

            cum_contrib += year_contrib
            cum_interest += year_interest

            schedule.append(
                TvmScheduleEntryModel(
                    period=y * m,
                    year=y,
                    startBalance=round(start_balance, 2),
                    contributions=round(year_contrib, 2),
                    interestEarned=round(year_interest, 2),
                    endBalance=round(current_balance, 2),
                    totalContributionsToDate=round(cum_contrib, 2),
                    totalInterestToDate=round(cum_interest, 2),
                )
            )

        return schedule

    async def calculate_rebalance(self, req: RebalanceCalculateRequest) -> RebalanceCalculateResponse:
        currency = req.currency or "USD"
        holdings = await self.valuation_service.get_portfolio_holdings(tab_id="all", currency=currency)
        open_positions = holdings.openPositions or []

        class_map: dict[str, list] = {}
        for pos in open_positions:
            atype = pos.assetType or "us-stock"
            class_map.setdefault(atype, []).append(pos)

        ordered_types = list(DEFAULT_TARGETS.keys())
        all_types = [t for t in ordered_types if t in class_map] + [t for t in class_map if t not in ordered_types]

        total_portfolio_value = sum(pos.holdingValue for pos in open_positions)

        groups: list[AssetClassRebalanceGroupModel] = []
        orders: list[RebalanceTradeOrderModel] = []
        total_buy_amount = 0.0
        total_sell_amount = 0.0
        total_inflow_contribution = 0.0

        for atype in all_types:
            pos_list = class_map[atype]
            class_total_value = sum(pos.holdingValue for pos in pos_list)
            class_portfolio_pct = (
                (class_total_value / total_portfolio_value * 100.0) if total_portfolio_value > 0 else 0.0
            )

            target_sum = sum(max(0.0, req.targetAllocations.get(p.symbol, 0.0)) for p in pos_list)
            is_valid = abs(target_sum - 100.0) <= 0.1 or (target_sum == 0 and len(pos_list) == 0)

            symbols: list[SymbolRebalanceItemModel] = []
            group_buy = 0.0
            group_sell = 0.0
            min_inflow_req = 0.0

            if req.mode == "standard":
                for pos in pos_list:
                    tpct = max(0.0, req.targetAllocations.get(pos.symbol, 0.0))
                    tval = (tpct / 100.0) * class_total_value if class_total_value > 0 else 0.0
                    delta_val = tval - pos.holdingValue
                    cur_class_pct = (pos.holdingValue / class_total_value * 100.0) if class_total_value > 0 else 0.0
                    cur_port_pct = (
                        (pos.holdingValue / total_portfolio_value * 100.0) if total_portfolio_value > 0 else 0.0
                    )

                    act: RebalanceAction
                    if delta_val > 0.01:
                        act = "BUY"
                        group_buy += delta_val
                        dshares = delta_val / pos.currentPrice if pos.currentPrice > 0 else 0.0
                    elif delta_val < -0.01:
                        act = "SELL"
                        group_sell += abs(delta_val)
                        dshares = -abs(delta_val) / pos.currentPrice if pos.currentPrice > 0 else 0.0
                    else:
                        act = "BALANCED"
                        dshares = 0.0

                    symbols.append(
                        SymbolRebalanceItemModel(
                            symbol=pos.symbol,
                            displaySymbol=pos.displaySymbol or pos.symbol,
                            name=pos.name or pos.symbol,
                            assetType=atype,
                            assetTypeLabel=pos.assetTypeLabel or atype,
                            currency=currency,
                            currentShares=pos.totalShares,
                            currentPrice=pos.currentPrice,
                            currentValue=pos.holdingValue,
                            currentClassPercent=round(cur_class_pct, 2),
                            currentPortfolioPercent=round(cur_port_pct, 2),
                            targetPercent=round(tpct, 2),
                            targetValue=round(tval, 2),
                            action=act,
                            deltaValue=round(delta_val, 2),
                            deltaShares=round(dshares, 4),
                            color="#3b82f6",
                        )
                    )
            else:
                # No-Sell mode
                if req.noSellSubMode == "min-inflow":
                    max_req_class_val = class_total_value
                    anchor_sym = None
                    for pos in pos_list:
                        tpct = max(0.0, req.targetAllocations.get(pos.symbol, 0.0))
                        if tpct > 0:
                            req_val = pos.holdingValue / (tpct / 100.0)
                            if req_val > max_req_class_val:
                                max_req_class_val = req_val
                                anchor_sym = pos.symbol

                    min_inflow_req = max(0.0, max_req_class_val - class_total_value)
                    new_class_val = max_req_class_val
                    group_buy = min_inflow_req
                    total_inflow_contribution += min_inflow_req

                    for pos in pos_list:
                        tpct = max(0.0, req.targetAllocations.get(pos.symbol, 0.0))
                        tval = (tpct / 100.0) * new_class_val
                        delta_val = max(0.0, tval - pos.holdingValue)
                        cur_class_pct = (pos.holdingValue / class_total_value * 100.0) if class_total_value > 0 else 0.0
                        cur_port_pct = (
                            (pos.holdingValue / total_portfolio_value * 100.0) if total_portfolio_value > 0 else 0.0
                        )
                        is_anchor = pos.symbol == anchor_sym or delta_val < 0.01

                        no_sell_act: RebalanceAction = "BUY" if delta_val >= 0.01 else "BALANCED"
                        dshares = delta_val / pos.currentPrice if delta_val >= 0.01 and pos.currentPrice > 0 else 0.0

                        symbols.append(
                            SymbolRebalanceItemModel(
                                symbol=pos.symbol,
                                displaySymbol=pos.displaySymbol or pos.symbol,
                                name=pos.name or pos.symbol,
                                assetType=atype,
                                assetTypeLabel=pos.assetTypeLabel or atype,
                                currency=currency,
                                currentShares=pos.totalShares,
                                currentPrice=pos.currentPrice,
                                currentValue=pos.holdingValue,
                                currentClassPercent=round(cur_class_pct, 2),
                                currentPortfolioPercent=round(cur_port_pct, 2),
                                targetPercent=round(tpct, 2),
                                targetValue=round(tval, 2),
                                action=no_sell_act,
                                deltaValue=round(delta_val, 2),
                                deltaShares=round(dshares, 4),
                                color="#3b82f6",
                                isAnchorPosition=is_anchor and tpct > 0,
                            )
                        )
                else:
                    # Custom Deposit Mode
                    deposit = max(0.0, req.customCashDeposit)
                    share_of_deposit = (
                        (class_total_value / total_portfolio_value * deposit)
                        if total_portfolio_value > 0
                        else (deposit / max(1, len(all_types)))
                    )
                    target_class_val = class_total_value + share_of_deposit

                    deficits = []
                    for pos in pos_list:
                        tpct = max(0.0, req.targetAllocations.get(pos.symbol, 0.0))
                        ideal_val = (tpct / 100.0) * target_class_val
                        deficit = max(0.0, ideal_val - pos.holdingValue)
                        deficits.append((pos.symbol, tpct, deficit))

                    tot_deficit = sum(d[2] for d in deficits)
                    allocated_cash = 0.0

                    for pos in pos_list:
                        sym, tpct, dval = next((d for d in deficits if d[0] == pos.symbol), (pos.symbol, 0.0, 0.0))
                        if tot_deficit > 0 and share_of_deposit > 0:
                            if tot_deficit <= share_of_deposit:
                                surplus = share_of_deposit - tot_deficit
                                b_amt = dval + (tpct / 100.0) * surplus
                            else:
                                b_amt = share_of_deposit * (dval / tot_deficit)
                        else:
                            b_amt = 0.0

                        allocated_cash += b_amt
                        tval = pos.holdingValue + b_amt
                        cur_class_pct = (pos.holdingValue / class_total_value * 100.0) if class_total_value > 0 else 0.0
                        cur_port_pct = (
                            (pos.holdingValue / total_portfolio_value * 100.0) if total_portfolio_value > 0 else 0.0
                        )

                        custom_act: RebalanceAction = "BUY" if b_amt >= 0.01 else "BALANCED"
                        dshares = b_amt / pos.currentPrice if b_amt >= 0.01 and pos.currentPrice > 0 else 0.0

                        symbols.append(
                            SymbolRebalanceItemModel(
                                symbol=pos.symbol,
                                displaySymbol=pos.displaySymbol or pos.symbol,
                                name=pos.name or pos.symbol,
                                assetType=atype,
                                assetTypeLabel=pos.assetTypeLabel or atype,
                                currency=currency,
                                currentShares=pos.totalShares,
                                currentPrice=pos.currentPrice,
                                currentValue=pos.holdingValue,
                                currentClassPercent=round(cur_class_pct, 2),
                                currentPortfolioPercent=round(cur_port_pct, 2),
                                targetPercent=round(tpct, 2),
                                targetValue=round(tval, 2),
                                action=custom_act,
                                deltaValue=round(b_amt, 2),
                                deltaShares=round(dshares, 4),
                                color="#3b82f6",
                                isAnchorPosition=b_amt < 0.01 and tpct > 0,
                            )
                        )

                    group_buy = allocated_cash
                    total_inflow_contribution += allocated_cash

            total_buy_amount += group_buy
            total_sell_amount += group_sell

            for s in symbols:
                if s.action == "BUY" and s.deltaValue >= 0.01:
                    orders.append(
                        RebalanceTradeOrderModel(
                            id=f"order-buy-{s.symbol}",
                            symbol=s.symbol,
                            displaySymbol=s.displaySymbol,
                            name=s.name,
                            assetType=s.assetType,
                            action="BUY",
                            shares=round(s.deltaShares, 4),
                            price=round(s.currentPrice, 4),
                            amount=round(s.deltaValue, 2),
                            currency=currency,
                        )
                    )
                elif s.action == "SELL" and s.deltaValue <= -0.01:
                    orders.append(
                        RebalanceTradeOrderModel(
                            id=f"order-sell-{s.symbol}",
                            symbol=s.symbol,
                            displaySymbol=s.displaySymbol,
                            name=s.name,
                            assetType=s.assetType,
                            action="SELL",
                            shares=round(abs(s.deltaShares), 4),
                            price=round(s.currentPrice, 4),
                            amount=round(abs(s.deltaValue), 2),
                            currency=currency,
                        )
                    )

            groups.append(
                AssetClassRebalanceGroupModel(
                    assetType=atype,
                    label=atype.replace("-", " ").title(),
                    color="#3b82f6",
                    currentValue=round(class_total_value, 2),
                    currentPortfolioPercent=round(class_portfolio_pct, 2),
                    targetTotalPercent=round(target_sum, 2),
                    isValid=is_valid,
                    minInflowRequired=round(min_inflow_req, 2),
                    totalBuyAmount=round(group_buy, 2),
                    totalSellAmount=round(group_sell, 2),
                    symbols=symbols,
                )
            )

        if req.mode == "standard":
            target_port_val = total_portfolio_value
        else:
            target_port_val = total_portfolio_value + total_inflow_contribution

        is_overall_valid = all(g.isValid for g in groups)
        orders.sort(key=lambda o: (-1 if o.action == "BUY" else 1, -o.amount))

        return RebalanceCalculateResponse(
            mode=req.mode,
            noSellSubMode=req.noSellSubMode,
            currency=currency,
            totalCurrentPortfolioValue=round(total_portfolio_value, 2),
            totalTargetPortfolioValue=round(target_port_val, 2),
            cashContribution=round(total_inflow_contribution if req.mode == "no-sell" else 0.0, 2),
            totalBuyAmount=round(total_buy_amount, 2),
            totalSellAmount=round(total_sell_amount, 2),
            netCashDifference=round(total_buy_amount - total_sell_amount, 2),
            groups=groups,
            orders=orders,
            isValid=is_overall_valid,
            errorMessage=""
            if is_overall_valid
            else "Target percentages in one or more asset classes do not sum to 100%.",
        )
