from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from models.portfolio import PortfolioHoldingsResponse, PortfolioPosition, PortfolioSummary
from models.transaction import Transaction
from services.dividend_service import DividendService


@pytest.fixture
def mock_valuation_service():
    service = MagicMock()
    # Mock holdings response
    summary = PortfolioSummary(
        totalInvested=100000.0,
        totalValue=120000.0,
        openInvested=100000.0,
        closedInvested=0.0,
        totalUnrealizedPL=20000.0,
        totalUnrealizedPLPercent=20.0,
        totalRealizedPL=0.0,
        totalRealizedPLPercent=0.0,
        totalReturn=20000.0,
        totalReturnPercent=20.0,
    )
    open_positions = [
        PortfolioPosition(
            symbol="PTT.BK",
            displaySymbol="PTT",
            name="PTT Public Company",
            assetType="thai-stock",
            assetTypeLabel="Thai Stock",
            totalShares=1000.0,
            totalCost=35000.0,
            averageCost=35.0,
            currentPrice=38.0,
            holdingValue=38000.0,
            unrealizedPL=3000.0,
            unrealizedPLPercent=8.57,
            currency="THB",
            originalCurrency="THB",
            hasPrice=True,
            lots=[],
        ),
        PortfolioPosition(
            symbol="AAPL",
            displaySymbol="AAPL",
            name="Apple Inc.",
            assetType="us-stock",
            assetTypeLabel="U.S. Stock",
            totalShares=10.0,
            totalCost=65000.0,
            averageCost=6500.0,
            currentPrice=7000.0,
            holdingValue=70000.0,
            unrealizedPL=5000.0,
            unrealizedPLPercent=7.69,
            currency="THB",
            originalCurrency="USD",
            hasPrice=True,
            lots=[],
        ),
        PortfolioPosition(
            symbol="K-USA-A(D).FUND",
            displaySymbol="K-USA-A(D)",
            name="K USA Fund",
            assetType="mutual-fund",
            assetTypeLabel="Mutual Fund",
            totalShares=500.0,
            totalCost=10000.0,
            averageCost=20.0,
            currentPrice=22.0,
            holdingValue=11000.0,
            unrealizedPL=1000.0,
            unrealizedPLPercent=10.0,
            currency="THB",
            originalCurrency="THB",
            hasPrice=True,
            lots=[],
        ),
    ]
    raw_txs = [
        Transaction(
            symbol="PTT.BK",
            date="2025-01-01",
            quantity=1000.0,
            price=35.0,
            currency="THB",
            assetType="thai-stock",
            txType="BUY",
        ),
        Transaction(
            symbol="AAPL",
            date="2025-01-01",
            quantity=10.0,
            price=180.0,
            currency="USD",
            assetType="us-stock",
            txType="BUY",
        ),
        Transaction(
            symbol="K-USA-A(D).FUND",
            date="2025-01-01",
            quantity=500.0,
            price=20.0,
            currency="THB",
            assetType="mutual-fund",
            txType="BUY",
        ),
    ]
    holdings_res = PortfolioHoldingsResponse(
        currency="THB",
        exchangeRate=35.0,
        tabId="all",
        summary=summary,
        openPositions=open_positions,
        closedPositions=[],
        rawTransactions=raw_txs,
    )
    service.get_portfolio_holdings = AsyncMock(return_value=holdings_res)
    return service


@pytest.fixture
def mock_price_service():
    service = MagicMock()
    service.fetch_stock_dividends = AsyncMock(
        return_value={
            "PTT.BK": {"trailing_12m_dps": 2.6, "dividends": [{"amount": 1.4, "date": 1759287600}]},
            "AAPL": {"trailing_12m_dps": 1.0, "dividends": [{"amount": 0.25, "date": 1762785000}]},
        }
    )
    return service


@pytest.fixture
def mock_nav_service():
    service = MagicMock()
    service.fetch_all_fund_dividends = AsyncMock(
        return_value={
            "K-USA-A(D).FUND": [
                {
                    "proj_id": "M0159_2555",
                    "class_abbr_name": "K-USA-A(D)",
                    "book_close_date": "2026-04-30",
                    "dividend_date": "2026-05-15",
                    "dividend_value": 0.5,
                }
            ]
        }
    )
    return service


@pytest.mark.asyncio
async def test_dividend_service_calculation(mock_valuation_service, mock_price_service, mock_nav_service):
    service = DividendService(
        valuation_service=mock_valuation_service,
        price_service=mock_price_service,
        nav_service=mock_nav_service,
    )

    res = await service.get_dividend_analytics(currency="THB", tab_id="all")

    assert res.error is None
    assert res.currency == "THB"
    assert res.exchangeRate == 35.0

    # Verify records parsed purely from API feeds (1 PTT, 1 AAPL, 1 K-USA)
    assert len(res.records) == 3

    # Check PTT API record (1000 shares * 1.4 DPS = 1400 THB gross, 140 THB WHT, 1260 THB net)
    ptt_rec = next(r for r in res.records if r.symbol == "PTT.BK")
    assert ptt_rec.grossAmount == 1400.0
    assert ptt_rec.withholdingTax == 140.0
    assert ptt_rec.netAmount == 1260.0
    assert ptt_rec.withholdingTaxRate == 10.0

    # Check AAPL API record (10 shares * 0.25 USD DPS = 2.5 USD -> 87.5 THB, WHT 15%: 0.375 USD -> 13.125 THB, Net: 2.125 USD -> 74.375 THB)
    aapl_rec = next(r for r in res.records if r.symbol == "AAPL")
    assert aapl_rec.grossAmount == 2.5
    assert aapl_rec.withholdingTax == 0.375
    assert aapl_rec.withholdingTaxRate == 15.0
    assert aapl_rec.convertedGrossAmount == pytest.approx(87.5)
    assert aapl_rec.convertedNetAmount == pytest.approx(74.375)

    # Check K-USA-A(D) SEC record (500 shares * 0.5 THB = 250 THB gross, 25 THB WHT, 225 THB net)
    k_usa_rec = next(r for r in res.records if r.symbol == "K-USA-A(D).FUND")
    assert k_usa_rec.grossAmount == 250.0
    assert k_usa_rec.withholdingTax == 25.0
    assert k_usa_rec.netAmount == 225.0

    # Check Annual Summaries (2025 and 2026)
    assert len(res.annualDividends) == 2
    years = [a.year for a in res.annualDividends]
    assert 2025 in years
    assert 2026 in years

    # Check Asset Type Summaries
    asset_types = {at.assetType for at in res.assetTypeSummaries}
    assert "thai-stock" in asset_types
    assert "us-stock" in asset_types
    assert "crypto" not in asset_types

    # Check Yield on Cost (YOC) calculation
    ptt_sum = next(s for s in res.symbolSummaries if s.symbol == "PTT.BK")
    # PTT: 1000 shares * 2.6 DPS = 2600 THB projected income on 35000 THB cost = 7.43% YOC
    assert ptt_sum.trailingAnnualDPS == 2.6
    assert ptt_sum.projectedAnnualIncome == pytest.approx(2600.0)
    assert ptt_sum.yieldOnCostPercent == pytest.approx((2600.0 / 35000.0) * 100.0)

    # Check Mutual Fund SEC Distribution
    fund_sum = next(s for s in res.symbolSummaries if "K-USA" in s.symbol)
    assert len(fund_sum.recentDistributions) == 1
    assert fund_sum.recentDistributions[0].dividendValue == 0.5
    assert fund_sum.recentDistributions[0].dividendDate == "2026-05-15"


@pytest.mark.asyncio
async def test_dividend_service_shares_on_ex_date():
    """Verify that dividend calculations respect exact share quantities held on ex-dates."""
    service = DividendService()

    # Position currently open with 500 shares
    pos = PortfolioPosition(
        symbol="ADVANC.BK",
        displaySymbol="ADVANC",
        name="Advanced Info Service",
        assetType="thai-stock",
        assetTypeLabel="Thai Stock",
        totalShares=500.0,
        totalCost=100000.0,
        averageCost=200.0,
        currentPrice=220.0,
        holdingValue=110000.0,
        unrealizedPL=10000.0,
        unrealizedPLPercent=10.0,
        currency="THB",
        originalCurrency="THB",
        hasPrice=True,
        lots=[],
    )

    # Trade history: Bought 300 on 2025-01-10, Bought 700 on 2025-06-01, Sold 500 on 2025-10-01
    raw_txs = [
        Transaction(
            symbol="ADVANC.BK",
            date="2025-01-10",
            quantity=300.0,
            price=200.0,
            currency="THB",
            assetType="thai-stock",
            txType="BUY",
        ),
        Transaction(
            symbol="ADVANC.BK",
            date="2025-06-01",
            quantity=700.0,
            price=205.0,
            currency="THB",
            assetType="thai-stock",
            txType="BUY",
        ),
        Transaction(
            symbol="ADVANC.BK",
            date="2025-10-01",
            quantity=-500.0,
            price=215.0,
            currency="THB",
            assetType="thai-stock",
            txType="SELL",
        ),
    ]

    # Dividend events:
    # Event 1 on 2025-04-15 (User held 300 shares): DPS 4.0 -> 300 * 4.0 = 1200 gross
    # Event 2 on 2025-08-20 (User held 300 + 700 = 1000 shares): DPS 5.0 -> 1000 * 5.0 = 5000 gross
    # Event 3 on 2025-11-15 (User held 1000 - 500 = 500 shares): DPS 4.5 -> 500 * 4.5 = 2250 gross
    stock_div_data = {
        "ADVANC.BK": {
            "trailing_12m_dps": 9.5,
            "dividends": [
                {"amount": 4.0, "date": int(datetime(2025, 4, 15, tzinfo=timezone.utc).timestamp())},
                {"amount": 5.0, "date": int(datetime(2025, 8, 20, tzinfo=timezone.utc).timestamp())},
                {"amount": 4.5, "date": int(datetime(2025, 11, 15, tzinfo=timezone.utc).timestamp())},
            ],
        }
    }

    res = service.calculate_dividend_analytics(
        open_positions=[pos],
        closed_positions=[],
        raw_transactions=raw_txs,
        stock_div_data=stock_div_data,
        fund_div_data={},
        exchange_rate=1.0,
        target_currency="THB",
        total_portfolio_value=110000.0,
        total_open_invested=100000.0,
    )

    assert len(res.records) == 3
    # Records are newest first
    r3 = next(r for r in res.records if r.date == "2025-11-15")
    r2 = next(r for r in res.records if r.date == "2025-08-20")
    r1 = next(r for r in res.records if r.date == "2025-04-15")

    assert r1.shares == 300.0
    assert r1.grossAmount == 1200.0
    assert r1.withholdingTax == 120.0
    assert r1.netAmount == 1080.0

    assert r2.shares == 1000.0
    assert r2.grossAmount == 5000.0
    assert r2.withholdingTax == 500.0
    assert r2.netAmount == 4500.0

    assert r3.shares == 500.0
    assert r3.grossAmount == 2250.0
    assert r3.withholdingTax == 225.0
    assert r3.netAmount == 2025.0
