from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from models.portfolio import (
    ClosedPortfolioPosition,
    PortfolioHoldingsResponse,
    PortfolioPosition,
    PortfolioSummary,
)
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
    assert "mutual-fund" in asset_types
    assert "bond" in asset_types
    assert "crypto" not in asset_types

    # Verify per-asset-type Yield on Cost calculations
    thai_at = next(at for at in res.assetTypeSummaries if at.assetType == "thai-stock")
    assert thai_at.totalCostBasis == 35000.0
    assert thai_at.currentValue == 38000.0
    assert thai_at.projectedAnnualDividends == pytest.approx(2600.0)
    assert thai_at.yieldOnCostPercent == pytest.approx((2600.0 / 35000.0) * 100.0)
    assert thai_at.currentYieldPercent == pytest.approx((2600.0 / 38000.0) * 100.0)

    us_at = next(at for at in res.assetTypeSummaries if at.assetType == "us-stock")
    assert us_at.totalCostBasis == 65000.0
    assert us_at.currentValue == 70000.0
    assert us_at.projectedAnnualDividends == pytest.approx(350.0)
    assert us_at.yieldOnCostPercent == pytest.approx((350.0 / 65000.0) * 100.0)
    assert us_at.currentYieldPercent == pytest.approx((350.0 / 70000.0) * 100.0)

    fund_at = next(at for at in res.assetTypeSummaries if at.assetType == "mutual-fund")
    assert fund_at.totalCostBasis == 10000.0
    assert fund_at.currentValue == 11000.0
    assert fund_at.projectedAnnualDividends == pytest.approx(250.0)
    assert fund_at.yieldOnCostPercent == pytest.approx((250.0 / 10000.0) * 100.0)
    assert fund_at.currentYieldPercent == pytest.approx((250.0 / 11000.0) * 100.0)

    bond_at = next(at for at in res.assetTypeSummaries if at.assetType == "bond")
    assert bond_at.totalCostBasis == 0.0
    assert bond_at.currentValue == 0.0
    assert bond_at.projectedAnnualDividends == 0.0
    assert bond_at.yieldOnCostPercent == 0.0
    assert bond_at.currentYieldPercent == 0.0

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


def test_dividend_mutual_fund_book_close_snapshot():
    """Verify mutual funds snapshot shares on book_close_date, ignoring post-close sales before dividend_date."""
    service = DividendService()

    pos = PortfolioPosition(
        symbol="SCBDV.FUND",
        displaySymbol="SCBDV",
        name="SCB Dividend Stock Fund",
        assetType="mutual-fund",
        assetTypeLabel="Mutual Fund",
        totalShares=400.0,
        totalCost=4000.0,
        averageCost=10.0,
        currentPrice=12.0,
        holdingValue=4800.0,
        unrealizedPL=800.0,
        unrealizedPLPercent=20.0,
        currency="THB",
        originalCurrency="THB",
        hasPrice=True,
        lots=[],
    )

    # User bought 1,000 units on 2025-01-01
    # Book close date is 2026-04-30 (entitlement snapshot taken on 1,000 units)
    # User sold 600 units on 2026-05-02 (after book close, before payment)
    # Dividend payment date is 2026-05-15
    raw_txs = [
        Transaction(
            symbol="SCBDV.FUND",
            date="2025-01-01",
            quantity=1000.0,
            price=10.0,
            currency="THB",
            assetType="mutual-fund",
            txType="BUY",
        ),
        Transaction(
            symbol="SCBDV.FUND",
            date="2026-05-02",
            quantity=-600.0,
            price=11.5,
            currency="THB",
            assetType="mutual-fund",
            txType="SELL",
        ),
    ]

    fund_div_data = {
        "SCBDV.FUND": [
            {
                "proj_id": "M0001",
                "class_abbr_name": "SCBDV",
                "book_close_date": "2026-04-30",
                "dividend_date": "2026-05-15",
                "dividend_value": 0.50,
            }
        ]
    }

    res = service.calculate_dividend_analytics(
        open_positions=[pos],
        closed_positions=[],
        raw_transactions=raw_txs,
        stock_div_data={},
        fund_div_data=fund_div_data,
        exchange_rate=1.0,
        target_currency="THB",
        total_portfolio_value=4800.0,
        total_open_invested=4000.0,
    )

    assert len(res.records) == 1
    rec = res.records[0]
    # Entitlement must be 1,000 units (held on 2026-04-30), NOT 400 units (after 2026-05-02 sell)!
    assert rec.shares == 1000.0
    assert rec.date == "2026-05-15"
    assert rec.recordDate == "2026-04-30"
    assert rec.dividendPerShare == 0.50
    assert rec.grossAmount == 500.0
    assert rec.withholdingTax == 50.0  # 10%
    assert rec.netAmount == 450.0


def test_dividend_cash_and_outflow_tx_types():
    """Verify that dividend cash rows are ignored for share balance, and positive outflow quantities are subtracted."""
    service = DividendService()

    pos = PortfolioPosition(
        symbol="MSFT",
        displaySymbol="MSFT",
        name="Microsoft Corporation",
        assetType="us-stock",
        assetTypeLabel="U.S. Stock",
        totalShares=500.0,
        totalCost=100000.0,
        averageCost=200.0,
        currentPrice=400.0,
        holdingValue=200000.0,
        unrealizedPL=100000.0,
        unrealizedPLPercent=100.0,
        currency="USD",
        originalCurrency="USD",
        hasPrice=True,
        lots=[],
    )

    # 1. Buy 1000 shares
    # 2. Recorded dividend cash income of $500 (must NOT be treated as 500 shares!)
    # 3. Sell 400 shares with positive quantity in CSV (quantity=400, txType="SELL")
    # 4. Exchange out 100 shares (quantity=100, txType="EXCHANGE_OUT")
    raw_txs = [
        Transaction(
            symbol="MSFT",
            date="2025-01-01",
            quantity=1000.0,
            price=200.0,
            currency="USD",
            assetType="us-stock",
            txType="BUY",
        ),
        Transaction(
            symbol="MSFT",
            date="2025-03-01",
            quantity=500.0,
            price=1.0,
            currency="USD",
            assetType="us-stock",
            txType="DIVIDEND",
        ),
        Transaction(
            symbol="MSFT",
            date="2025-06-01",
            quantity=400.0,  # Positive quantity with SELL txType
            price=220.0,
            currency="USD",
            assetType="us-stock",
            txType="SELL",
        ),
        Transaction(
            symbol="MSFT",
            date="2025-07-01",
            quantity=100.0,  # Positive quantity with EXCHANGE_OUT txType
            price=225.0,
            currency="USD",
            assetType="us-stock",
            txType="EXCHANGE_OUT",
            exchangeTo="GOOGL",
        ),
    ]

    stock_div_data = {
        "MSFT": {
            "trailing_12m_dps": 3.0,
            "dividends": [
                {"amount": 0.80, "date": int(datetime(2025, 8, 15, tzinfo=timezone.utc).timestamp())},
            ],
        }
    }

    res = service.calculate_dividend_analytics(
        open_positions=[pos],
        closed_positions=[],
        raw_transactions=raw_txs,
        stock_div_data=stock_div_data,
        fund_div_data={},
        exchange_rate=35.0,
        target_currency="USD",
        total_portfolio_value=200000.0,
        total_open_invested=100000.0,
    )

    assert len(res.records) == 1
    rec = res.records[0]
    # Net shares on 2025-08-15: 1000 (buy) + 0 (cash div) - 400 (sell) - 100 (exchange out) = 500
    assert rec.shares == 500.0
    assert rec.dividendPerShare == 0.80
    assert rec.grossAmount == 400.0
    assert rec.withholdingTax == 60.0  # 15% for US stocks
    assert rec.netAmount == 340.0


def test_dividend_bond_vehicle_calculation():
    """Verify dividend payout calculation and ledger values for the bond vehicle."""
    service = DividendService()

    pos = PortfolioPosition(
        symbol="BND",
        displaySymbol="BND",
        name="Vanguard Total Bond Market ETF",
        assetType="bond",
        assetTypeLabel="Bond",
        totalShares=100.0,
        totalCost=7400.0,
        averageCost=74.0,
        currentPrice=75.0,
        holdingValue=7500.0,
        unrealizedPL=100.0,
        unrealizedPLPercent=1.35,
        currency="USD",
        originalCurrency="USD",
        hasPrice=True,
        lots=[],
    )

    raw_txs = [
        Transaction(
            symbol="BND",
            date="2025-01-01",
            quantity=100.0,
            price=74.0,
            currency="USD",
            assetType="bond",
            txType="BUY",
        )
    ]

    stock_div_data = {
        "BND": {
            "trailing_12m_dps": 2.5,
            "dividends": [
                {"amount": 0.22, "date": int(datetime(2025, 2, 1, tzinfo=timezone.utc).timestamp())},
                {"amount": 0.23, "date": int(datetime(2025, 3, 1, tzinfo=timezone.utc).timestamp())},
            ],
        }
    }

    res = service.calculate_dividend_analytics(
        open_positions=[pos],
        closed_positions=[],
        raw_transactions=raw_txs,
        stock_div_data=stock_div_data,
        fund_div_data={},
        exchange_rate=35.0,
        target_currency="THB",
        total_portfolio_value=7500.0 * 35.0,
        total_open_invested=7400.0 * 35.0,
    )

    assert len(res.records) == 2
    # Verify bond records with 15% WHT rate
    for r in res.records:
        assert r.assetType == "bond"
        assert r.shares == 100.0
        assert r.withholdingTaxRate == 15.0
        assert r.grossAmount == pytest.approx(r.dividendPerShare * 100.0)
        assert r.withholdingTax == pytest.approx(r.grossAmount * 0.15)
        assert r.netAmount == pytest.approx(r.grossAmount * 0.85)
        assert r.convertedGrossAmount == pytest.approx(r.grossAmount * 35.0)

    # Check bond asset type summary
    bond_sum = next(at for at in res.assetTypeSummaries if at.assetType == "bond")
    assert bond_sum.recordCount == 2
    assert bond_sum.totalGrossDividends == pytest.approx((22.0 + 23.0) * 35.0)
    assert bond_sum.totalNetDividends == pytest.approx(((22.0 * 0.85) + (23.0 * 0.85)) * 35.0)


def test_dividend_closed_position_history():
    """Verify closed positions retain dividend payouts earned when open, but not after closing."""
    service = DividendService()

    closed_pos = ClosedPortfolioPosition(
        symbol="TSLA",
        displaySymbol="TSLA",
        name="Tesla Inc",
        assetType="us-stock",
        assetTypeLabel="U.S. Stock",
        totalShares=0.0,
        closedShares=100.0,
        totalCost=20000.0,
        totalProceeds=25000.0,
        realizedPL=5000.0,
        realizedPLPercent=25.0,
        averageBuyPrice=200.0,
        averageSellPrice=250.0,
        currency="USD",
        originalCurrency="USD",
        lots=[],
    )

    # Bought 100 shares on 2024-01-01, Sold 100 shares on 2024-12-31
    # Dividend 1 on 2024-06-15: Held 100 shares -> earned!
    # Dividend 2 on 2025-06-15: Held 0 shares -> not earned!
    raw_txs = [
        Transaction(
            symbol="TSLA",
            date="2024-01-01",
            quantity=100.0,
            price=200.0,
            currency="USD",
            assetType="us-stock",
            txType="BUY",
        ),
        Transaction(
            symbol="TSLA",
            date="2024-12-31",
            quantity=-100.0,
            price=250.0,
            currency="USD",
            assetType="us-stock",
            txType="SELL",
        ),
    ]

    stock_div_data = {
        "TSLA": {
            "trailing_12m_dps": 1.0,
            "dividends": [
                {"amount": 1.0, "date": int(datetime(2024, 6, 15, tzinfo=timezone.utc).timestamp())},
                {"amount": 1.5, "date": int(datetime(2025, 6, 15, tzinfo=timezone.utc).timestamp())},
            ],
        }
    }

    res = service.calculate_dividend_analytics(
        open_positions=[],
        closed_positions=[closed_pos],
        raw_transactions=raw_txs,
        stock_div_data=stock_div_data,
        fund_div_data={},
        exchange_rate=1.0,
        target_currency="USD",
    )

    # Only 1 dividend should be recorded (from 2024-06-15)
    assert len(res.records) == 1
    assert res.records[0].date == "2024-06-15"
    assert res.records[0].shares == 100.0
    assert res.records[0].grossAmount == 100.0
    assert res.records[0].netAmount == 85.0


def test_dividend_shares_held_strictly_before_ex_date():
    """Verify share snapshot is evaluated strictly before ex-date (buys/sells on ex-date do not affect eligibility)."""
    service = DividendService()

    pos = PortfolioPosition(
        symbol="NVDA",
        displaySymbol="NVDA",
        name="NVIDIA Corporation",
        assetType="us-stock",
        assetTypeLabel="U.S. Stock",
        totalShares=150.0,
        totalCost=15000.0,
        averageCost=100.0,
        currentPrice=120.0,
        holdingValue=18000.0,
        unrealizedPL=3000.0,
        unrealizedPLPercent=20.0,
        currency="USD",
        originalCurrency="USD",
        hasPrice=True,
        lots=[],
    )

    # Ex-dividend date is 2025-06-11
    # 1. Bought 100 shares on 2025-06-10 (Day before ex-date -> ENTITLED to dividend)
    # 2. Bought 50 shares on 2025-06-11 (ON ex-date -> NOT entitled to this dividend)
    # 3. Sold 20 shares on 2025-06-11 (ON ex-date -> Still entitled, does not forfeit dividend)
    raw_txs = [
        Transaction(
            symbol="NVDA",
            date="2025-06-10",
            quantity=100.0,
            price=100.0,
            currency="USD",
            assetType="us-stock",
            txType="BUY",
        ),
        Transaction(
            symbol="NVDA",
            date="2025-06-11",
            quantity=50.0,
            price=105.0,
            currency="USD",
            assetType="us-stock",
            txType="BUY",
        ),
        Transaction(
            symbol="NVDA",
            date="2025-06-11",
            quantity=-20.0,
            price=105.0,
            currency="USD",
            assetType="us-stock",
            txType="SELL",
        ),
    ]

    stock_div_data = {
        "NVDA": {
            "trailing_12m_dps": 0.40,
            "dividends": [
                {"amount": 0.10, "date": int(datetime(2025, 6, 11, tzinfo=timezone.utc).timestamp())},
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
        target_currency="USD",
        total_portfolio_value=18000.0,
        total_open_invested=15000.0,
    )

    assert len(res.records) == 1
    rec = res.records[0]
    # Snapshot strictly before ex-date (2025-06-11) is 100.0 shares
    assert rec.shares == 100.0
    assert rec.dividendPerShare == 0.10
    assert rec.grossAmount == 10.0
    assert rec.withholdingTax == 1.50
    assert rec.netAmount == 8.50


