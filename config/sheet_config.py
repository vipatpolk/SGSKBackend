from typing import Any

from config.settings import get_settings

SHEET_CONFIG: dict[str, Any] = {
    "baseUrl": "https://docs.google.com/spreadsheets/d",
    "gids": {
        "us-stock": "1032243687",
        "thai-stock": "102823823",
        "crypto": "1822302220",
        "mutual-fund": "359978839",
        "closed-position": "273600915",
    },
}

ASSET_TABS = [
    {"id": "all", "label": "All", "sheetGid": "", "currency": ""},
    {"id": "us-stock", "label": "U.S. Stock", "sheetGid": SHEET_CONFIG["gids"]["us-stock"], "currency": "USD"},
    {"id": "thai-stock", "label": "Thai Stock", "sheetGid": SHEET_CONFIG["gids"]["thai-stock"], "currency": "THB"},
    {"id": "crypto", "label": "Cryptocurrency", "sheetGid": SHEET_CONFIG["gids"]["crypto"], "currency": "THB"},
    {"id": "mutual-fund", "label": "Mutual Fund", "sheetGid": SHEET_CONFIG["gids"]["mutual-fund"], "currency": "THB"},
    {
        "id": "closed-position",
        "label": "Closed Position",
        "sheetGid": SHEET_CONFIG["gids"]["closed-position"],
        "currency": "",
    },
]


def get_sheet_export_url(gid: str) -> str:
    settings = get_settings()
    return f"{SHEET_CONFIG['baseUrl']}/{settings.google_spreadsheet_id}/export?format=csv&gid={gid}"
