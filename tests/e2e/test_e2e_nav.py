import pytest


@pytest.mark.e2e
def test_e2e_fetch_navs_post(api_client, mocked_external_apis):
    payload = {"symbols": ["K-CHANGE.BKFUND"]}
    response = api_client.post("/nav/fetch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
