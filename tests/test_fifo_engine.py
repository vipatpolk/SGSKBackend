import pytest
from models.transaction import Transaction
from services.share_lot_service import ShareLotService

@pytest.fixture
def service():
    return ShareLotService()

def test_fifo_single_buy_and_hold(service):
    transactions = [
        Transaction(symbol="AAPL", date="2026-01-01", quantity=10, price=100.0, currency="USD", assetType="us-stock")
    ]
    summaries, closed_summaries, tx_summaries = service.process_transactions(transactions)

    # Open summary check
    assert len(summaries) == 1
    s = summaries[0]
    assert s.symbol == "AAPL"
    assert s.totalShares == 10.0
    assert s.totalCost == 1000.0
    assert s.averageCost == 100.0
    assert len(s.lots) == 1

    # Closed summaries check
    assert len(closed_summaries) == 0

    # Transaction summaries check
    assert len(tx_summaries) == 1
    ts = tx_summaries[0]
    assert ts.buyCount == 1
    assert ts.sellCount == 0
    assert ts.currentStatus == "OPEN"

def test_fifo_partial_lot_sale(service):
    transactions = [
        Transaction(symbol="AAPL", date="2026-01-01", quantity=10, price=100.0, currency="USD", assetType="us-stock"),
        Transaction(symbol="AAPL", date="2026-01-05", quantity=-4, price=150.0, currency="USD", assetType="us-stock")
    ]
    summaries, closed_summaries, tx_summaries = service.process_transactions(transactions)

    # Open lot remaining: 6 shares @ $100 = $600
    assert len(summaries) == 1
    s = summaries[0]
    assert s.totalShares == 6.0
    assert s.totalCost == 600.0
    assert s.averageCost == 100.0

    # Transaction summary realized P/L check
    # Sold 4 shares @ $150 ($600 proceeds) - cost 4 @ $100 ($400) = +$200 P/L (50%)
    ts = tx_summaries[0]
    assert ts.realizedPL == 200.0
    assert pytest.approx(ts.realizedPLPercent, 0.01) == 50.0

def test_fifo_multi_lot_queue_matching(service):
    transactions = [
        Transaction(symbol="AAPL", date="2026-01-01", quantity=5, price=100.0, currency="USD", assetType="us-stock"),
        Transaction(symbol="AAPL", date="2026-01-02", quantity=5, price=200.0, currency="USD", assetType="us-stock"),
        Transaction(symbol="AAPL", date="2026-01-03", quantity=-7, price=250.0, currency="USD", assetType="us-stock")
    ]
    summaries, closed_summaries, tx_summaries = service.process_transactions(transactions)

    # FIFO order:
    # Lot 1 (5 @ $100) completely consumed (cost 500)
    # Lot 2 (5 @ $200) partially consumed (2 shares, cost 400)
    # Remaining in open lot: 3 shares @ $200 = $600 cost
    assert len(summaries) == 1
    s = summaries[0]
    assert s.totalShares == 3.0
    assert s.totalCost == 600.0
    assert s.averageCost == 200.0

    # Realized P/L calculation:
    # Lot 1 proceeds (5 * 250 = 1250) - cost 500 = +750
    # Lot 2 proceeds (2 * 250 = 500) - cost 400 = +100
    # Total P/L = +850. Realized cost basis = 900.
    ts = tx_summaries[0]
    assert pytest.approx(ts.realizedPL, 0.01) == 850.0

def test_fifo_complete_position_exit(service):
    transactions = [
        Transaction(symbol="TSLA", date="2026-01-01", quantity=10, price=200.0, currency="USD", assetType="us-stock"),
        Transaction(symbol="TSLA", date="2026-01-15", quantity=-10, price=250.0, currency="USD", assetType="us-stock")
    ]
    summaries, closed_summaries, tx_summaries = service.process_transactions(transactions)

    # Position is completely closed -> open summaries is empty
    assert len(summaries) == 0

    # Closed summaries has 1 item
    assert len(closed_summaries) == 1
    cs = closed_summaries[0]
    assert cs.symbol == "TSLA"
    assert cs.closedShares == 10.0
    assert cs.totalCost == 2000.0
    assert cs.totalProceeds == 2500.0
    assert cs.realizedPL == 500.0
    assert pytest.approx(cs.realizedPLPercent, 0.01) == 25.0

    # Transaction summary status
    ts = tx_summaries[0]
    assert ts.currentStatus == "CLOSED"
    assert ts.netShares == 0.0

def test_fifo_floating_point_epsilon_precision(service):
    # Tests that micro-decimal crypto amounts don't leave phantom open lots due to precision loss
    transactions = [
        Transaction(symbol="BTC.CRYPTO", date="2026-01-01", quantity=0.12345678, price=50000.0, currency="USD", assetType="crypto"),
        Transaction(symbol="BTC.CRYPTO", date="2026-01-02", quantity=-0.12345678, price=60000.0, currency="USD", assetType="crypto")
    ]
    summaries, closed_summaries, tx_summaries = service.process_transactions(transactions)

    assert len(summaries) == 0
    assert len(closed_summaries) == 1
    assert closed_summaries[0].closedShares == pytest.approx(0.12345678, 1e-7)
