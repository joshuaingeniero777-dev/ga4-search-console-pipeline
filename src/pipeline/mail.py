"""Sending alert emails from the alerts mailbox (docs/decisions.md, decision 25).

The mailbox (ALERT_SENDER, e.g. alerts@joinswc.org) signed in once with
scripts/authorize_alert_mailbox.py and allowed "send email" only. That saved
permission (ALERT_REFRESH_TOKEN) can send as that one mailbox and nothing else:
it can't read mail or send as anyone else.

Needs, in .env or the host's secret settings:
    ALERT_SENDER                the mailbox address
    ALERT_REFRESH_TOKEN         written by the authorize script; a secret, never print it
    GOOGLE_OAUTH_CLIENT_ID      the same sign-in client the control panel uses
    GOOGLE_OAUTH_CLIENT_SECRET
If any is missing, there's no sender and alerts stay off (pipeline/alerts.py).
"""

import base64
import os
from email.message import EmailMessage

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
TOKEN_URI = "https://oauth2.googleapis.com/token"
FROM_NAME = "SWC data pipeline"

SENDER_ENV = "ALERT_SENDER"
REFRESH_TOKEN_ENV = "ALERT_REFRESH_TOKEN"
CLIENT_ID_ENV = "GOOGLE_OAUTH_CLIENT_ID"
CLIENT_SECRET_ENV = "GOOGLE_OAUTH_CLIENT_SECRET"


def message(sender: str, recipients: list[str], subject: str, body: str) -> EmailMessage:
    email = EmailMessage()
    email["From"] = f"{FROM_NAME} <{sender}>"
    email["To"] = ", ".join(recipients)
    email["Subject"] = subject
    email.set_content(body)
    return email


class GmailSender:
    def __init__(self, sender: str, refresh_token: str, client_id: str, client_secret: str, service=None):
        self.sender = sender
        if service is None:
            permission = Credentials(
                None,
                refresh_token=refresh_token,
                token_uri=TOKEN_URI,
                client_id=client_id,
                client_secret=client_secret,
                scopes=[GMAIL_SEND_SCOPE],
            )
            service = build("gmail", "v1", credentials=permission, cache_discovery=False)
        self._service = service

    def send(self, recipients: list[str], subject: str, body: str) -> None:
        raw = base64.urlsafe_b64encode(message(self.sender, recipients, subject, body).as_bytes()).decode()
        self._service.users().messages().send(userId="me", body={"raw": raw}).execute()


def configured_sender() -> GmailSender | None:
    """The alerts mailbox's sender, or None if it isn't fully set up (then alerts stay off)."""
    load_dotenv()
    values = [os.environ.get(name, "").strip() for name in (SENDER_ENV, REFRESH_TOKEN_ENV, CLIENT_ID_ENV, CLIENT_SECRET_ENV)]
    return GmailSender(*values) if all(values) else None
