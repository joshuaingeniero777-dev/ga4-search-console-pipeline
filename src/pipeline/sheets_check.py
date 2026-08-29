"""Write a test row to Google Sheets to prove the write path works.

This is the 'load' end of the pipeline. Building it before the extract
end means that when GA4 access arrives, only one thing is untested.
"""

import os
from datetime import datetime, timezone

import gspread
from dotenv import load_dotenv
from google.oauth2 import service_account

KEY_PATH = "service-account.json"

# Sheets needs a WRITE scope, unlike the read-only scopes in auth_check.
# Scopes are per-token, so a script that only reads should not request this.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def main() -> None:
    # Reads .env into the environment. Does nothing if the file is absent,
    # which is what we want in production where real env vars are set instead.
    load_dotenv()

    spreadsheet_id = os.environ["SPREADSHEET_ID"]

    credentials = service_account.Credentials.from_service_account_file(
        KEY_PATH, scopes=SCOPES
    )
    client = gspread.authorize(credentials)

    # open_by_key uses the ID from the URL. There is also open_by_title,
    # but titles are not unique and can be renamed, so IDs are safer.
    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.sheet1

    timestamp = datetime.now(timezone.utc).isoformat()
    worksheet.append_row(["test", timestamp, "written by pipeline-runner"])

    print(f"Wrote a row to: {spreadsheet.title}")
    print(f"Rows now in sheet: {worksheet.row_count}")


if __name__ == "__main__":
    main()