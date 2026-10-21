"""Verify service account credentials work, independent of property access.

Run this to distinguish 'my key is broken' from 'nobody has granted me
access yet'. Those look similar from a failed API call but have completely
different fixes, so it's worth being able to test them separately.
"""

from google.auth.transport.requests import Request

from pipeline.google_auth import READONLY_SCOPES
from pipeline.google_auth import credentials as load_credentials


def main() -> None:
    credentials = load_credentials(READONLY_SCOPES)

    print(f"Service account: {credentials.service_account_email}")

    # The actual test. This sends the signed key to Google and asks for a
    # short-lived access token in exchange. Valid key, token comes back.
    # No property access involved, so this works even while access is pending.
    credentials.refresh(Request())

    print(f"Access token obtained: {credentials.token[:12]}...")
    print("Authentication works.")


if __name__ == "__main__":
    main()