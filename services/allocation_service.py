from models.allocation import (
    CurrencyExposure,
    HoldingConcentration,
    PortfolioAllocationResponse,
    RebalanceRecommendation,
)
from services.valuation_service import ValuationService
from utils.format_utils import get_asset_type_label

DEFAULT_TARGETS: dict[str, float] = {
    "us-stock": 40.0,
    "thai-stock": 30.0,
    "crypto": 15.0,
    "mutual-fund": 15.0,
    "bond": 0.0,
}


class AllocationService:
    def __init__(self, valuation_service: ValuationService | None = None):
        self.valuation_service = valuation_service or ValuationService()

    async def calculate_allocation(
        self,
        targets: dict[str, float] | None = None,
        currency: str = "THB",
    ) -> PortfolioAllocationResponse:
        target_currency = currency.upper()
        target_allocation = targets if targets is not None else DEFAULT_TARGETS

        holdings_res = await self.valuation_service.get_portfolio_holdings(tab_id="all", currency=target_currency)
        if holdings_res.error:
            return PortfolioAllocationResponse(
                currency=target_currency,
                exchangeRate=holdings_res.exchangeRate,
                totalPortfolioValue=0.0,
                recommendations=[],
                currencyExposure=CurrencyExposure(usd=0.0, thb=0.0, usdPercent=0.0, thbPercent=0.0),
                holdingsConcentration=[],
                error=holdings_res.error,
            )

        return self.process_allocation(
            holdings_res=holdings_res,
            targets=target_allocation,
        )

    def process_allocation(
        self,
        holdings_res,
        targets: dict[str, float],
    ) -> PortfolioAllocationResponse:
        current_values: dict[str, float] = {k: 0.0 for k in DEFAULT_TARGETS}

        usd_val = 0.0
        thb_val = 0.0

        for pos in holdings_res.openPositions:
            val = pos.holdingValue
            asset_type = pos.assetType
            current_values[asset_type] = current_values.get(asset_type, 0.0) + val

            orig = pos.originalCurrency.upper()
            if orig in ("USD", "USDT"):
                usd_val += val
            elif orig == "THB":
                thb_val += val

        total_value = sum(current_values.values())

        # Recommendations
        default_keys = list(DEFAULT_TARGETS.keys())
        all_keys = list(default_keys)
        for k in list(current_values.keys()) + list(targets.keys()):
            if k not in all_keys:
                all_keys.append(k)

        recommendations: list[RebalanceRecommendation] = []
        for k in all_keys:
            val = current_values.get(k, 0.0)
            actual_pct = (val / total_value * 100.0) if total_value > 0 else 0.0
            target_pct = targets.get(k, 0.0)
            target_val = (target_pct / 100.0) * total_value
            rebalance_amount = target_val - val
            deviation_pct = actual_pct - target_pct

            if abs(rebalance_amount) < 0.01:
                action = "BALANCED"
            elif rebalance_amount > 0:
                action = "BUY"
            else:
                action = "SELL"

            recommendations.append(
                RebalanceRecommendation(
                    assetType=k,
                    label=get_asset_type_label(k),
                    currentValue=val,
                    actualPercent=actual_pct,
                    targetPercent=target_pct,
                    rebalanceAmount=rebalance_amount,
                    deviationPercent=deviation_pct,
                    action=action,
                )
            )

        # Currency Exposure
        tot_curr = usd_val + thb_val
        currency_exposure = CurrencyExposure(
            usd=usd_val,
            thb=thb_val,
            usdPercent=(usd_val / tot_curr * 100.0) if tot_curr > 0 else 0.0,
            thbPercent=(thb_val / tot_curr * 100.0) if tot_curr > 0 else 0.0,
        )

        # Holding Concentration
        holdings_concentration: list[HoldingConcentration] = []
        for pos in holdings_res.openPositions:
            if pos.holdingValue > 0 or pos.totalShares > 0:
                class_tot = current_values.get(pos.assetType, 0.0)
                port_pct = (pos.holdingValue / total_value * 100.0) if total_value > 0 else 0.0
                class_pct = (pos.holdingValue / class_tot * 100.0) if class_tot > 0 else 0.0

                holdings_concentration.append(
                    HoldingConcentration(
                        symbol=pos.symbol,
                        displaySymbol=pos.displaySymbol,
                        name=pos.name,
                        assetType=pos.assetType,
                        value=pos.holdingValue,
                        portfolioPercent=port_pct,
                        classPercent=class_pct,
                    )
                )

        holdings_concentration.sort(key=lambda x: x.value, reverse=True)

        return PortfolioAllocationResponse(
            currency=holdings_res.currency,
            exchangeRate=holdings_res.exchangeRate,
            totalPortfolioValue=total_value,
            recommendations=recommendations,
            currencyExposure=currency_exposure,
            holdingsConcentration=holdings_concentration,
            error=None,
        )
