import re


def normalize_asset_type(raw_type: str) -> str | None:
    if not raw_type:
        return None
    normalized = raw_type.strip().lower()
    if "thai-stock" == normalized or "thai" in normalized or normalized == "th":
        return "thai-stock"
    if "us-stock" == normalized or "u.s" in normalized or "us stock" in normalized or "united states" in normalized:
        return "us-stock"
    if "crypto" == normalized or "crypto" in normalized:
        return "crypto"
    if "mutual-fund" == normalized or "fund" in normalized or "mutual" in normalized:
        return "mutual-fund"
    return None


def get_asset_type(asset_type: str | None = None, symbol: str | None = None) -> str:
    non_asset_types = {"closed-position", "all", "unknown"}
    if asset_type and asset_type not in non_asset_types:
        normalized = normalize_asset_type(asset_type)
        if normalized:
            return normalized
        return asset_type

    if symbol:
        sym = symbol.upper()
        if sym.endswith(".FUND") or sym.endswith(".BKFUND"):
            return "mutual-fund"
        if sym.endswith(".BK"):
            return "thai-stock"
        if sym.endswith(".CRYPTO"):
            return "crypto"
    return "us-stock"


def to_yahoo_symbol(symbol: str) -> str:
    if not symbol:
        return ""
    trimmed = symbol.strip()
    if trimmed.upper().endswith(".FUND"):
        return trimmed[:-5]
    if trimmed.upper().endswith(".BKFUND"):
        return trimmed[:-7]
    if trimmed.upper().endswith(".BK"):
        return trimmed
    if trimmed.upper().endswith(".CRYPTO"):
        return trimmed[:-7]
    return trimmed.replace(".", "-").replace("/", "-")


def resolve_quote_currency(quote: str) -> str:
    if not quote:
        return ""
    q = quote.upper()
    if q == "THB":
        return "THB"
    if "USD" in q or q == "DAI":
        return "USD"
    return q


def display_symbol(symbol: str) -> str:
    if not symbol:
        return ""
    return re.sub(r"(?i)\.(FUND|BKFUND|BK|CRYPTO)$", "", symbol.strip())


def convert_currency(amount: float, from_curr: str, to_curr: str, exchange_rate: float) -> float:
    norm_from = "USD" if from_curr.upper() == "USDT" else from_curr.upper()
    norm_to = "USD" if to_curr.upper() == "USDT" else to_curr.upper()

    if norm_from == norm_to:
        return amount
    if exchange_rate <= 0:
        return amount

    if norm_from == "USD" and norm_to == "THB":
        return amount * exchange_rate
    if norm_from == "THB" and norm_to == "USD":
        return amount / exchange_rate

    return amount


ASSET_TYPE_LABELS: dict[str, str] = {
    "us-stock": "U.S. Stock",
    "thai-stock": "Thai Stock",
    "crypto": "Cryptocurrency",
    "mutual-fund": "Mutual Fund",
}


def get_asset_type_label(asset_type: str | None = None, symbol: str | None = None) -> str:
    t = get_asset_type(asset_type, symbol)
    return ASSET_TYPE_LABELS.get(t, t.replace("-", " ").title())
