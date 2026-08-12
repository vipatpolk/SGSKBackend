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


@pytest.mark.unit
def test_parse_exported_5_column_csv_roundtrip(service):
    """TC-BE-01: Verify exported 5-column CSV string with BOM marker parses back correctly."""
    exported_csv = "\uFEFFSymbol,Date,Quantity,Price,Currency\r\nAAPL,2026-01-05,10,150.00,USD\r\nAAPL,2026-01-20,-8,170.00,USD\r\nBTC.CRYPTO,2026-02-01,0.5,95000.00,USD\r\n"
    transactions = service.parse_csv(exported_csv, "all")

    assert len(transactions) == 3
    assert transactions[0].symbol == "AAPL"
    assert transactions[0].quantity == 10.0
    assert transactions[1].symbol == "AAPL"
    assert transactions[1].quantity == -8.0
    assert transactions[2].symbol == "BTC.CRYPTO"
    assert transactions[2].assetType == "crypto"

