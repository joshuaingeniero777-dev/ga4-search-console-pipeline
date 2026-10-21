"""Sending alert emails from the alerts mailbox. Gmail is faked; nothing is ever sent."""

import base64
import email

import pytest
from google.auth.exceptions import RefreshError

from pipeline import mail
from pipeline.errors import explain_error
from scripts.authorize_alert_mailbox import save_to_env

SENDER = "alerts@joinswc.org"
SETTINGS = {
    mail.SENDER_ENV: SENDER,
    mail.REFRESH_TOKEN_ENV: "pretend-refresh-token",
    mail.CLIENT_ID_ENV: "client.apps.googleusercontent.com",
    mail.CLIENT_SECRET_ENV: "pretend-secret",
}


class FakeGmail:
    def __init__(self):
        self.sent = []

    def users(self):
        return self

    def messages(self):
        return self

    def send(self, userId, body):
        self.sent.append((userId, body))
        return self

    def execute(self):
        return {"id": "123"}


def test_sends_as_the_mailbox_to_every_recipient():
    gmail = FakeGmail()
    sender = mail.GmailSender(SENDER, "token", "id", "secret", service=gmail)

    sender.send(["owner@joinswc.org", "marisol@starrwellnesscollective.org"], "Website numbers dropped", "Hi,\n…")

    [(user, body)] = gmail.sent
    assert user == "me"
    sent = email.message_from_bytes(base64.urlsafe_b64decode(body["raw"]))
    assert sent["From"] == f"SWC data pipeline <{SENDER}>"
    assert sent["To"] == "owner@joinswc.org, marisol@starrwellnesscollective.org"
    assert sent["Subject"] == "Website numbers dropped"
    assert "Hi," in sent.get_payload(decode=True).decode()


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setattr(mail, "load_dotenv", lambda: None)
    monkeypatch.setattr(mail, "build", lambda *a, **k: FakeGmail())
    for name, value in SETTINGS.items():
        monkeypatch.setenv(name, value)
    return monkeypatch


def test_sender_is_ready_when_everything_is_set(env):
    sender = mail.configured_sender()
    assert isinstance(sender, mail.GmailSender) and sender.sender == SENDER


@pytest.mark.parametrize("missing", list(SETTINGS))
def test_no_sender_if_anything_is_missing(env, missing):
    env.delenv(missing)
    assert mail.configured_sender() is None


def test_withdrawn_permission_is_explained():
    message = explain_error(RefreshError("invalid_grant: Token has been expired or revoked."), "Gmail")
    assert "alerts mailbox's permission to send email has run out" in message
    assert "scripts/authorize_alert_mailbox.py" in message


# --- saving the permission to .env -----------------------------------------------------

def test_saving_adds_the_line_and_leaves_everything_else(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SPREADSHEET_ID=abc\n# a comment\nALERT_SENDER=alerts@joinswc.org", encoding="utf-8")

    save_to_env(env_file, "ALERT_REFRESH_TOKEN", "new-token")

    assert env_file.read_text(encoding="utf-8") == (
        "SPREADSHEET_ID=abc\n# a comment\nALERT_SENDER=alerts@joinswc.org\nALERT_REFRESH_TOKEN=new-token\n"
    )


def test_saving_again_replaces_the_old_value(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("ALERT_REFRESH_TOKEN=old\nOTHER=1\n", encoding="utf-8")

    save_to_env(env_file, "ALERT_REFRESH_TOKEN", "new\\1-token")  # backslashes must survive as-is

    assert env_file.read_text(encoding="utf-8") == "ALERT_REFRESH_TOKEN=new\\1-token\nOTHER=1\n"
