from typing import Any

SHEET_CONFIG: dict[str, Any] = {
    "baseUrl": "https://docs.google.com/spreadsheets/d",
    "spreadsheetId": "1gc98SMT2mJOaKZC15JWxflZk_GASAW_1m72_Ex8CnFQ",
    "gids": {
        "us-stock": "1032243687",
        "thai-stock": "102823823",
        "crypto": "1822302220",
        "mutual-fund": "359978839",
        "closed-position": "273600915",
    }
}

ASSET_TABS = [
    {"id": "all", "label": "All", "sheetGid": "", "currency": ""},
    {"id": "us-stock", "label": "U.S. Stock", "sheetGid": SHEET_CONFIG["gids"]["us-stock"], "currency": "USD"},
    {"id": "thai-stock", "label": "Thai Stock", "sheetGid": SHEET_CONFIG["gids"]["thai-stock"], "currency": "THB"},
    {"id": "crypto", "label": "Cryptocurrency", "sheetGid": SHEET_CONFIG["gids"]["crypto"], "currency": "THB"},
    {"id": "mutual-fund", "label": "Mutual Fund", "sheetGid": SHEET_CONFIG["gids"]["mutual-fund"], "currency": "THB"},
    {"id": "closed-position", "label": "Closed Position", "sheetGid": SHEET_CONFIG["gids"]["closed-position"], "currency": ""},
]

def get_sheet_export_url(gid: str) -> str:
    return f"{SHEET_CONFIG['baseUrl']}/{SHEET_CONFIG['spreadsheetId']}/export?format=csv&gid={gid}"
