"""One-time sign-in that lets the pipeline send alert emails from the alerts mailbox.

Run from the repo root, after ALERT_SENDER is in .env:

    python scripts/authorize_alert_mailbox.py

A browser opens on Google's sign-in page. Sign in AS THE ALERTS MAILBOX (not your
own account) and allow "Send email on your behalf". The script checks it really
was that mailbox, then saves the permission to .env as ALERT_REFRESH_TOKEN. It
never prints it.

Run it again if alerts ever say the mailbox's permission has run out (for example
after its password was changed).
"""

import re
import sys
from pathlib import Path

from dotenv import dotenv_values
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google_auth_oauthlib.flow import InstalledAppFlow

from pipeline.mail import (
    CLIENT_ID_ENV,
    CLIENT_SECRET_ENV,
    GMAIL_SEND_SCOPE,
    REFRESH_TOKEN_ENV,
    SENDER_ENV,
)

ENV_FILE = Path(".env")
PORT = 8765  # must match the redirect URI added to the sign-in client: http://localhost:8765/
SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email", GMAIL_SEND_SCOPE]


def save_to_env(path: Path, name: str, value: str) -> None:
    """Set NAME=value in .env, replacing an existing line or adding one. Other lines are untouched."""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    line = f"{name}={value}"
    pattern = re.compile(rf"^{re.escape(name)}=.*$", re.MULTILINE)
    text = pattern.sub(lambda _: line, text, count=1) if pattern.search(text) else text.rstrip("\n") + f"\n{line}\n"
    path.write_text(text, encoding="utf-8")


def fail(reason: str) -> None:
    print(f"Not saved. {reason}")
    sys.exit(1)


def main() -> None:
    env = dotenv_values(ENV_FILE)
    sender = (env.get(SENDER_ENV) or "").strip().lower()
    client_id, client_secret = (env.get(CLIENT_ID_ENV) or "").strip(), (env.get(CLIENT_SECRET_ENV) or "").strip()
    if not sender:
        fail(f"Add {SENDER_ENV}=<the alerts mailbox address> to .env first.")
    if not (client_id and client_secret):
        fail(f"{CLIENT_ID_ENV} and {CLIENT_SECRET_ENV} need to be in .env (the control panel's sign-in client).")

    flow = InstalledAppFlow.from_client_config(
        {"web": {"client_id": client_id, "client_secret": client_secret,
                 "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token"}},
        scopes=SCOPES,
    )
    print(f"A browser window is opening. Sign in as {sender} and allow it to send email.")
    permission = flow.run_local_server(
        port=PORT, open_browser=True, login_hint=sender, access_type="offline", prompt="consent",
        authorization_prompt_message="", success_message="Done. You can close this tab and go back to the terminal.",
    )

    signed_in_as = id_token.verify_oauth2_token(permission.id_token, Request(), client_id).get("email", "").lower()
    if signed_in_as != sender:
        fail(f"You signed in as {signed_in_as}, not {sender}. Run it again and choose {sender}.")
    if not permission.refresh_token:
        fail("Google didn't hand over a lasting permission. Run it again.")

    save_to_env(ENV_FILE, REFRESH_TOKEN_ENV, permission.refresh_token)
    print(f"Saved. Alerts can now be sent from {sender}. (The permission is in .env and wasn't shown here.)")


if __name__ == "__main__":
    main()
