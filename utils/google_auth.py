import json
import os

from google.auth.transport.requests import Request
from google.oauth2 import service_account

from config.settings import get_settings

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def get_google_auth_headers() -> dict[str, str]:
    settings = get_settings()
    sa_info = settings.google_service_account_json.strip()
    if not sa_info:
        return {}

    try:
        if os.path.exists(sa_info):
            creds = service_account.Credentials.from_service_account_file(sa_info, scopes=SCOPES)
        else:
            info_dict = json.loads(sa_info)
            creds = service_account.Credentials.from_service_account_info(info_dict, scopes=SCOPES)

        creds.refresh(Request())
        if creds.token:
            return {"Authorization": f"Bearer {creds.token}"}
    except Exception as e:
        print(f"[GoogleAuth] Failed to obtain service account token: {e}")

    return {}
