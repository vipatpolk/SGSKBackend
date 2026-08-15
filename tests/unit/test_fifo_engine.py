import pytest

from models.transaction import Transaction
from services.share_lot_service import ShareLotService


@pytest.fixture
def service():
    return ShareLotService()


@pytest.mark.unit
def test_fifo_single_buy_and_hold(service):
    transactions = [
        Transaction(symbol="AAPL", date="2026-01-01", quantity=10, price=100.0, currency="USD", assetType="us-stock")
    ]
    summaries, closed_summaries, tx_summaries = service.process_transactions(transactions)

    assert len(summaries) == 1
    s = summaries[0]
    assert s.symbol == "AAPL"
    assert s.totalShares == 10.0
    assert s.totalCost == 1000.0
    assert s.averageCost == 100.0
    assert len(s.lots) == 1

    assert len(closed_summaries) == 0

    assert len(tx_summaries) == 1
    ts = tx_summaries[0]
    assert ts.buyCount == 1
    assert ts.sellCount == 0
    assert ts.currentStatus == "OPEN"


@pytest.mark.unit
def test_fifo_partial_lot_sale(service):
    transactions = [
        Transaction(symbol="AAPL", date="2026-01-01", quantity=10, price=100.0, currency="USD", assetType="us-stock"),
        Transaction(symbol="AAPL", date="2026-01-05", quantity=-4, price=150.0, currency="USD", assetType="us-stock"),
    ]
    summaries, closed_summaries, tx_summaries = service.process_transactions(transactions)

    assert len(summaries) == 1
    s = summaries[0]
    assert s.totalShares == 6.0
    assert s.totalCost == 600.0
    assert s.averageCost == 100.0

    ts = tx_summaries[0]
    assert ts.realizedPL == 200.0
    assert pytest.approx(ts.realizedPLPercent, 0.01) == 50.0


@pytest.mark.unit
def test_fifo_multi_lot_queue_matching(service):
    transactions = [
        Transaction(symbol="AAPL", date="2026-01-01", quantity=5, price=100.0, currency="USD", assetType="us-stock"),
        Transaction(symbol="AAPL", date="2026-01-02", quantity=5, price=200.0, currency="USD", assetType="us-stock"),
        Transaction(symbol="AAPL", date="2026-01-03", quantity=-7, price=250.0, currency="USD", assetType="us-stock"),
    ]
    summaries, closed_summaries, tx_summaries = service.process_transactions(transactions)

    assert len(summaries) == 1
    s = summaries[0]
    assert s.totalShares == 3.0
    assert s.totalCost == 600.0
    assert s.averageCost == 200.0

    ts = tx_summaries[0]
    assert pytest.approx(ts.realizedPL, 0.01) == 850.0


@pytest.mark.unit
def test_fifo_complete_position_exit(service):
    transactions = [
        Transaction(symbol="TSLA", date="2026-01-01", quantity=10, price=200.0, currency="USD", assetType="us-stock"),
        Transaction(symbol="TSLA", date="2026-01-15", quantity=-10, price=250.0, currency="USD", assetType="us-stock"),
    ]
    summaries, closed_summaries, tx_summaries = service.process_transactions(transactions)

    assert len(summaries) == 0

    assert len(closed_summaries) == 1
    cs = closed_summaries[0]
    assert cs.symbol == "TSLA"
    assert cs.closedShares == 10.0
    assert cs.totalCost == 2000.0
    assert cs.totalProceeds == 2500.0
    assert cs.realizedPL == 500.0
    assert pytest.approx(cs.realizedPLPercent, 0.01) == 25.0

    ts = tx_summaries[0]
    assert ts.currentStatus == "CLOSED"
    assert ts.netShares == 0.0


@pytest.mark.unit
def test_fifo_floating_point_epsilon_precision(service):
    transactions = [
        Transaction(
            symbol="BTC.CRYPTO",
            date="2026-01-01",
            quantity=0.12345678,
            price=50000.0,
            currency="USD",
            assetType="crypto",
        ),
        Transaction(
            symbol="BTC.CRYPTO",
            date="2026-01-02",
            quantity=-0.12345678,
            price=60000.0,
            currency="USD",
            assetType="crypto",
        ),
    ]
    summaries, closed_summaries, tx_summaries = service.process_transactions(transactions)

    assert len(summaries) == 0
    assert len(closed_summaries) == 1
    assert closed_summaries[0].closedShares == pytest.approx(0.12345678, 1e-7)
