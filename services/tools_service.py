import logging

from models.tools import (
    PositionSnapshotModel,
    SimulateOrderRequest,
    SimulateOrderResponse,
    SimulationDeltaMetrics,
    SimulationStateMetrics,
    SolveTargetCostRequest,
    SolveTargetCostResponse,
)
from services.valuation_service import ValuationService

logger = logging.getLogger(__name__)


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
