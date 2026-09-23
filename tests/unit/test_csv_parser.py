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
def test_parse_bond_csv(service):
    csv_text = """Symbol,Date,Quantity,Price,Price Currency
BND,2025-10-14,0.5770158,74.6080,USD
TLT,2025-10-27,0.0415716,91.1680,USD
BND,2025-11-18,-0.7527750,74.2320,USD
"""
    transactions = service.parse_csv(csv_text, "bond")
    assert len(transactions) == 3
    assert transactions[0].symbol == "BND"
    assert transactions[0].assetType == "bond"
    assert transactions[0].quantity == 0.5770158
    assert transactions[0].price == 74.6080
    assert transactions[0].currency == "USD"
    assert transactions[1].symbol == "TLT"
    assert transactions[1].assetType == "bond"
    assert transactions[2].symbol == "BND"
    assert transactions[2].quantity == -0.7527750
    assert transactions[2].assetType == "bond"


@pytest.mark.unit
def test_parse_exported_5_column_csv_roundtrip(service):
    """TC-BE-01: Verify exported 5-column CSV string with BOM marker parses back correctly."""
    exported_csv = "\ufeffSymbol,Date,Quantity,Price,Currency\r\nAAPL,2026-01-05,10,150.00,USD\r\nAAPL,2026-01-20,-8,170.00,USD\r\nBTC.CRYPTO,2026-02-01,0.5,95000.00,USD\r\n"
    transactions = service.parse_csv(exported_csv, "all")

    assert len(transactions) == 3
    assert transactions[0].symbol == "AAPL"
    assert transactions[0].quantity == 10.0
    assert transactions[1].symbol == "AAPL"
    assert transactions[1].quantity == -8.0
    assert transactions[2].symbol == "BTC.CRYPTO"
    assert transactions[2].assetType == "crypto"


@pytest.mark.unit
def test_parse_mutual_fund_exchange_csv(service):
    """Verify parsing mutual fund CSV with Exchange From and Exchange To columns."""
    csv_text = """Symbol,Date,Quantity,Price,Currency,Exchange From,Exchange To
K-USA,2026-03-01,100,15.5,THB,K-CASH,
K-CASH,2026-03-01,-1000,1.55,THB,,K-USA
"""
    transactions = service.parse_csv(csv_text, "mutual-fund")
    assert len(transactions) == 2

    t1 = transactions[0]
    assert t1.symbol == "K-USA"
    assert t1.quantity == 100.0
    assert t1.exchangeFrom == "K-CASH"
    assert t1.exchangeTo is None

    t2 = transactions[1]
    assert t2.symbol == "K-CASH"
    assert t2.quantity == -1000.0
    assert t2.exchangeFrom is None
    assert t2.exchangeTo == "K-USA"

    # Verify process_transactions correctly sets transaction type and exchange count
    _, _, summaries = service.process_transactions(transactions)
    k_usa_summary = next(s for s in summaries if s.symbol == "K-USA")
    assert k_usa_summary.exchangeCount == 1
    assert k_usa_summary.transactions[0].type == "EXCHANGE_IN"
    assert k_usa_summary.transactions[0].exchangeFrom == "K-CASH"

    k_cash_summary = next(s for s in summaries if s.symbol == "K-CASH")
    assert k_cash_summary.exchangeCount == 1
    assert k_cash_summary.transactions[0].type == "EXCHANGE_OUT"
    assert k_cash_summary.transactions[0].exchangeTo == "K-USA"


@pytest.mark.unit
def test_parse_provident_fund_csv(service):
    """Verify parsing Provident Fund CSV snapshot into Employee and Employer contribution lots."""
    pvd_csv = """Ticker,Employee's Unit,Employer's Unit,Total Value,Currency
PVDSP500,"8,294.68","6,005.29","205,135.89",THB
PVDWEQ,"18,919.08","13,853.91","410,227.49",THB
"""
    transactions = service.parse_csv(pvd_csv, "provident-fund")
    assert len(transactions) == 4

    sp500_txs = [t for t in transactions if t.symbol == "PVDSP500"]
    assert len(sp500_txs) == 2
    emp_tx = next(t for t in sp500_txs if t.note == "Employee Contribution")
    empr_tx = next(t for t in sp500_txs if t.note == "Employer Matching")

    assert emp_tx.quantity == 8294.68
    assert empr_tx.quantity == 6005.29
    assert emp_tx.currency == "THB"
    assert emp_tx.assetType == "provident-fund"

    # Total units = 14,299.97, nav = 205,135.89 / 14,299.97 = 14.345197...
    expected_nav = 205135.89 / (8294.68 + 6005.29)
    assert abs(emp_tx.price - expected_nav) < 1e-4

    # Verify process_transactions creates SymbolSummary with employeeShares and employerShares
    summaries, _, _ = service.process_transactions(transactions)
    sp500_summary = next(s for s in summaries if s.symbol == "PVDSP500")
    assert abs(sp500_summary.totalShares - (8294.68 + 6005.29)) < 1e-4
    assert sp500_summary.employeeShares == 8294.68
    assert sp500_summary.employerShares == 6005.29
    assert abs(sp500_summary.totalCost - 205135.89) < 0.1
    assert len(sp500_summary.lots) == 2
    assert sp500_summary.lots[0].note == "Employee Contribution"
    assert sp500_summary.lots[1].note == "Employer Matching"


@pytest.mark.unit
def test_parse_provident_fund_csv_new_structure(service):
    """Verify parsing Provident Fund CSV with Employee Contribution, Employee Earnings, Employer Matching, Employer Earnings."""
    pvd_csv = """Ticker,Employee's Unit,Employer's Unit,Employee's Contribution,Employee's Earnings,Employer's Matching,Employer's Earnings,Currency
PVDSP500,"8,294.68","6,005.29","100,858.26","18,130.55","73,962.72","12,184.36",THB
"""
    transactions = service.parse_csv(pvd_csv, "provident-fund")
    assert len(transactions) == 2

    emp_tx = next(t for t in transactions if t.note == "Employee Contribution")
    empr_tx = next(t for t in transactions if t.note == "Employer Matching")

    assert emp_tx.quantity == 8294.68
    assert empr_tx.quantity == 6005.29
    assert emp_tx.employeeContribution == 100858.26
    assert emp_tx.employeeEarnings == 18130.55
    assert empr_tx.employerMatching == 73962.72
    assert empr_tx.employerEarnings == 12184.36

    # Unit cost bases: 100858.26 / 8294.68 = 12.1594
    assert abs(emp_tx.price - (100858.26 / 8294.68)) < 1e-4
    assert abs(empr_tx.price - (73962.72 / 6005.29)) < 1e-4

    summaries, _, _ = service.process_transactions(transactions)
    assert len(summaries) == 1
    s = summaries[0]
    assert s.symbol == "PVDSP500"
    assert s.employeeShares == 8294.68
    assert s.employerShares == 6005.29
    assert s.employeeContribution == 100858.26
    assert s.employeeEarnings == 18130.55
    assert s.employerMatching == 73962.72
    assert s.employerEarnings == 12184.36
    assert abs(s.totalCost - (100858.26 + 73962.72)) < 1e-2

