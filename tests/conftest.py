import pytest
import httpx
from fastapi.testclient import TestClient
from main import app
from services.share_lot_service import ShareLotService
from services.price_service import PriceService
from services.nav_service import NavService

@pytest.fixture
def api_client():
    return TestClient(app)

@pytest.fixture
def share_lot_service():
    return ShareLotService()

@pytest.fixture
def sample_csv_us_stock():
    return """Symbol,Date,Quantity,Price,Currency,Asset Type
AAPL,2026-01-05,10,150.00,USD,us-stock
AAPL,2026-01-10,5,160.00,USD,us-stock
AAPL,2026-01-20,-8,170.00,USD,us-stock
NVDA,2026-01-15,4,500.00,USD,us-stock
"""

@pytest.fixture
def sample_csv_closed_position():
    return """Symbol,Date,Quantity,Price,Currency,Asset Type
TSLA,2026-01-01,10,200.00,USD,us-stock
TSLA,2026-01-15,-10,250.00,USD,us-stock
"""

@pytest.fixture
def sample_csv_thai_stock():
    return """Symbol,Date,Quantity,Price,Currency,Asset Type
PTT.BK,2026-01-02,"1,000",35.50,THB,thai-stock
PTT.BK,2026-01-12,-500,38.00,THB,thai-stock
"""
