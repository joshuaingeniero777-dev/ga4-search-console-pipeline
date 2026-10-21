"""One place to load the service account key, so every module finds it the same way.

Locally the key is service-account.json in the repo root. In the cloud the
host sets GOOGLE_APPLICATION_CREDENTIALS to wherever it mounted the key.
"""

import os

from google.oauth2 import service_account

KEY_PATH_ENV = "GOOGLE_APPLICATION_CREDENTIALS"
DEFAULT_KEY_PATH = "service-account.json"

# Read-only scopes for pulling reports. Even a leaked token from these
# could not modify anything in Analytics or Search Console.
READONLY_SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/webmasters.readonly",
]

# Sheets needs write access. Only code that writes should ask for it.
SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def key_path() -> str:
    return os.environ.get(KEY_PATH_ENV) or DEFAULT_KEY_PATH


def credentials(scopes: list[str]) -> service_account.Credentials:
    return service_account.Credentials.from_service_account_file(key_path(), scopes=scopes)
