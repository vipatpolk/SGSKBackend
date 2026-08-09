import pytest
from utils.format_utils import (
    normalize_asset_type,
    get_asset_type,
    to_yahoo_symbol,
    resolve_quote_currency
)

def test_normalize_asset_type():
    assert normalize_asset_type("US-Stock") == "us-stock"
    assert normalize_asset_type("thai stock") == "thai-stock"
    assert normalize_asset_type("TH") == "thai-stock"
    assert normalize_asset_type("crypto currency") == "crypto"
    assert normalize_asset_type("mutual fund") == "mutual-fund"
    assert normalize_asset_type("Unknown Type") is None
    assert normalize_asset_type("") is None

def test_get_asset_type():
    # Asset type override
    assert get_asset_type("thai-stock", "AAPL") == "thai-stock"
    assert get_asset_type("us-stock", "PTT.BK") == "us-stock"

    # Symbol suffix fallback when asset_type is non-asset category
    assert get_asset_type("closed-position", "PTT.BK") == "thai-stock"
    assert get_asset_type("all", "K-CHANGE.BKFUND") == "mutual-fund"
    assert get_asset_type("unknown", "BTC.CRYPTO") == "crypto"
    assert get_asset_type(None, "AAPL") == "us-stock"

def test_to_yahoo_symbol():
    assert to_yahoo_symbol("AAPL") == "AAPL"
    assert to_yahoo_symbol("BRK.B") == "BRK-B"
    assert to_yahoo_symbol("PTT.BK") == "PTT.BK"
    assert to_yahoo_symbol("K-CHANGE.BKFUND") == "K-CHANGE"
    assert to_yahoo_symbol("BTC.CRYPTO") == "BTC"
    assert to_yahoo_symbol("") == ""

def test_resolve_quote_currency():
    assert resolve_quote_currency("THB") == "THB"
    assert resolve_quote_currency("USD") == "USD"
    assert resolve_quote_currency("USDT") == "USD"
    assert resolve_quote_currency("DAI") == "USD"
    assert resolve_quote_currency("") == ""
