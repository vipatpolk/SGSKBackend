import pytest

from services.share_lot_service import ShareLotService


@pytest.fixture
def service():
    return ShareLotService()

@pytest.mark.unit
def test_parse_valid_csv(service, sample_csv_us_stock):
    transactions = service.parse_csv(sample_csv_us_stock, "us-stock")
    assert len(transactions) == 4

    t1 = transactions[0]
    assert t1.symbol == "AAPL"
    assert t1.date == "2026-01-05"
    assert t1.quantity == 10.0
    assert t1.price == 150.0
    assert t1.currency == "USD"
    assert t1.assetType == "us-stock"

    t3 = transactions[2]
    assert t3.symbol == "AAPL"
    assert t3.quantity == -8.0  # SELL transaction
    assert t3.price == 170.0

@pytest.mark.unit
def test_parse_comma_formatted_numbers(service, sample_csv_thai_stock):
    transactions = service.parse_csv(sample_csv_thai_stock, "thai-stock")
    assert len(transactions) == 2

    t1 = transactions[0]
    assert t1.symbol == "PTT.BK"
    assert t1.quantity == 1000.0
    assert t1.price == 35.50
    assert t1.currency == "THB"

@pytest.mark.unit
def test_parse_empty_or_header_only_csv(service):
    assert service.parse_csv("", "us-stock") == []
    assert service.parse_csv("Symbol,Date,Quantity,Price,Currency", "us-stock") == []

@pytest.mark.unit
def test_parse_csv_skips_malformed_rows(service):
    csv_text = """Symbol,Date,Quantity,Price,Currency
AAPL,2026-01-01,10,150.00,USD
INVALID_ROW_MISSING_COLUMNS
BAD_QTY,2026-01-02,INVALID_NUMBER,150.00,USD
NVDA,2026-01-03,5,500.00,USD
"""
    transactions = service.parse_csv(csv_text, "us-stock")
    assert len(transactions) == 2
    assert transactions[0].symbol == "AAPL"
    assert transactions[1].symbol == "NVDA"
