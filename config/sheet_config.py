from typing import Any

from config.settings import get_settings

SHEET_CONFIG: dict[str, Any] = {
    "baseUrl": "https://docs.google.com/spreadsheets/d",
    "gids": {
        "us-stock": "1032243687",
        "thai-stock": "102823823",
        "crypto": "1822302220",
        "mutual-fund": "359978839",
        "bond": "1657887056",
        "provident-fund": "0",
        "closed-position": "273600915",
    },
}

ASSET_TABS = [
    {"id": "all", "label": "All", "sheetGid": "", "currency": ""},
    {"id": "us-stock", "label": "U.S. Stock", "sheetGid": SHEET_CONFIG["gids"]["us-stock"], "currency": "USD"},
    {"id": "thai-stock", "label": "Thai Stock", "sheetGid": SHEET_CONFIG["gids"]["thai-stock"], "currency": "THB"},
    {"id": "crypto", "label": "Cryptocurrency", "sheetGid": SHEET_CONFIG["gids"]["crypto"], "currency": "THB"},
    {"id": "mutual-fund", "label": "Mutual Fund", "sheetGid": SHEET_CONFIG["gids"]["mutual-fund"], "currency": "THB"},
    {"id": "bond", "label": "Bond", "sheetGid": SHEET_CONFIG["gids"]["bond"], "currency": "USD"},
    {
        "id": "provident-fund",
        "label": "Provident Fund",
        "sheetGid": SHEET_CONFIG["gids"]["provident-fund"],
        "currency": "THB",
    },
    {
        "id": "closed-position",
        "label": "Closed Position",
        "sheetGid": SHEET_CONFIG["gids"]["closed-position"],
        "currency": "",
    },
]


def get_sheet_export_url(gid: str, tab_id: str | None = None, spreadsheet_id: str | None = None) -> str:
    settings = get_settings()
    sheet_id = spreadsheet_id
    if not sheet_id:
        if tab_id == "provident-fund":
            sheet_id = settings.google_pvd_spreadsheet_id
        else:
            sheet_id = settings.google_spreadsheet_id
    return f"{SHEET_CONFIG['baseUrl']}/{sheet_id}/export?format=csv&gid={gid}"

