import pytest
from fastapi.testclient import TestClient

from config.settings import get_settings
from main import app

client = TestClient(app)
settings = get_settings()
AUTH_HEADERS = {"X-API-Key": settings.backend_api_key}


def test_get_portfolio_dividend_unauthorized():
    response = client.get("/portfolio/dividend")
    assert response.status_code == 401


def test_get_portfolio_dividend_authorized():
    response = client.get("/portfolio/dividend?currency=THB", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "currency" in data
    assert data["currency"] == "THB"
    assert "totalGrossDividends" in data
    assert "totalNetDividends" in data
    assert "portfolioYieldOnCost" in data
    assert "annualDividends" in data
    assert "assetTypeSummaries" in data
    assert "symbolSummaries" in data
    assert "records" in data


def test_get_portfolio_dividend_usd():
    response = client.get("/portfolio/dividend?currency=USD", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["currency"] == "USD"
