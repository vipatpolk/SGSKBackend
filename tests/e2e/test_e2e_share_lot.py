import pytest


@pytest.mark.e2e
def test_e2e_get_share_lot_sheet_us_stock(api_client, mocked_external_apis):
    response = api_client.get("/share-lot/sheet/us-stock")
    assert response.status_code == 200
    data = response.json()

    assert "summaries" in data
    assert "totalCostByCurrency" in data
    assert data["totalCostByCurrency"]["USD"] > 0
    assert any(s["symbol"] == "AAPL" for s in data["summaries"])

@pytest.mark.e2e
def test_e2e_get_share_lot_sheet_invalid_tab(api_client):
    response = api_client.get("/share-lot/sheet/non-existent-tab")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "Invalid tab id" in data["error"]

@pytest.mark.e2e
def test_e2e_get_all_share_lots(api_client, mocked_external_apis):
    response = api_client.get("/share-lot/sheets")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "summaries" in data
    assert "totalCostByCurrency" in data
