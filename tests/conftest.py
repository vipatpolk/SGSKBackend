import json
import os
import re

import pytest
from fastapi.testclient import TestClient

from main import app
from services.nav_service import NavService
from services.price_service import PriceService
from services.share_lot_service import ShareLotService

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

@pytest.fixture
def api_client():
    return TestClient(app)

@pytest.fixture
def share_lot_service():
    return ShareLotService()

@pytest.fixture
def price_service():
    return PriceService()

@pytest.fixture
def nav_service():
    return NavService()

@pytest.fixture
def fixture_us_stock_csv():
    with open(os.path.join(FIXTURES_DIR, "sample_us_stock.csv"), encoding="utf-8") as f:
        return f.read()

@pytest.fixture
def fixture_thai_stock_csv():
    with open(os.path.join(FIXTURES_DIR, "sample_thai_stock.csv"), encoding="utf-8") as f:
        return f.read()

@pytest.fixture
def sample_csv_us_stock(fixture_us_stock_csv):
    return fixture_us_stock_csv

@pytest.fixture
def sample_csv_thai_stock(fixture_thai_stock_csv):
    return fixture_thai_stock_csv

@pytest.fixture
def sample_csv_closed_position():
    return """Symbol,Date,Quantity,Price,Currency,Asset Type
TSLA,2026-01-01,10,200.00,USD,us-stock
TSLA,2026-01-15,-10,250.00,USD,us-stock
"""

@pytest.fixture
def fixture_yahoo_finance_json():
    with open(os.path.join(FIXTURES_DIR, "sample_yahoo_finance.json"), encoding="utf-8") as f:
        return json.load(f)

@pytest.fixture
def fixture_binance_ticker_json():
    with open(os.path.join(FIXTURES_DIR, "sample_binance_ticker.json"), encoding="utf-8") as f:
        return json.load(f)

@pytest.fixture
def fixture_sec_nav_json():
    with open(os.path.join(FIXTURES_DIR, "sample_sec_nav.json"), encoding="utf-8") as f:
        return json.load(f)

@pytest.fixture
def mocked_external_apis(respx_mock, fixture_us_stock_csv, fixture_yahoo_finance_json, fixture_binance_ticker_json, fixture_sec_nav_json):
    """Mocks all third-party external HTTP calls (Google Sheets, Yahoo Finance, Binance TH, SEC Thailand)."""
    # Mock Google Sheet CSV export
    respx_mock.get(url=re.compile(r"https://docs\.google\.com/spreadsheets/.*")).respond(
        status_code=200,
        text=fixture_us_stock_csv
    )

    # Mock Yahoo Finance Quote API
    respx_mock.get(url=re.compile(r"https://query1\.finance\.yahoo\.com/.*")).respond(
        status_code=200,
        json=fixture_yahoo_finance_json
    )

    # Mock Binance TH Ticker API
    respx_mock.get(url=re.compile(r"https://api\.binance\.th/.*")).respond(
        status_code=200,
        json=fixture_binance_ticker_json
    )

    # Mock SEC Thailand NAV API
    respx_mock.get(url=re.compile(r"https://api\.sec\.or\.th/.*")).respond(
        status_code=200,
        json=fixture_sec_nav_json
    )

    return respx_mock
