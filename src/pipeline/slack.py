"""Posting alerts to the pipeline's Slack channel (docs/decisions.md, decision 26).

A Slack "incoming webhook" is a web address that posts into one channel. Anyone
who has it can post there, so it's a secret: it lives in .env (or the host's
secret settings) as SLACK_WEBHOOK_URL and must never be printed or logged.
Errors from here never include it.

Without SLACK_WEBHOOK_URL there's no sender and alerts stay off.
"""

import os

import requests
from dotenv import load_dotenv

from pipeline.errors import PipelineError

WEBHOOK_ENV = "SLACK_WEBHOOK_URL"
WEBHOOK_PREFIX = "https://hooks.slack.com/"  # anything else isn't a Slack webhook; don't send alert data there
TIMEOUT_SECONDS = 15

UNREACHABLE = "Couldn't reach Slack to post the alert. The next run will try again."
LINK_BROKEN = (
    "Slack refused the alert ({reason}). The pipeline's Slack link may have been removed or its channel "
    "deleted. Someone needs to make a new Slack link and put it in SLACK_WEBHOOK_URL (see the owner's guide)."
)
# What Slack says when the link itself no longer works (rather than a passing hiccup).
BROKEN_LINK_REASONS = {"no_service", "invalid_token", "channel_not_found", "channel_is_archived", "no_team",
                       "team_disabled", "action_prohibited", "posting_to_general_channel_denied"}


class SlackSender:
    service = "Slack"

    def __init__(self, webhook_url: str, post=requests.post):
        self._webhook_url = webhook_url
        self._post = post

    def where(self, recipients: list[str]) -> str:
        return "to the Slack channel"

    def send(self, recipients: list[str], subject: str, body: str) -> None:
        try:
            response = self._post(
                self._webhook_url, json={"text": f"*{subject}*\n\n{body}"}, timeout=TIMEOUT_SECONDS
            )
        except requests.RequestException:
            # The original error names the webhook address, so it's replaced, not chained.
            raise PipelineError(UNREACHABLE) from None
        reason = (response.text or "").strip()
        if response.status_code == 200 and reason == "ok":
            return
        if reason in BROKEN_LINK_REASONS or response.status_code in (403, 404, 410):
            raise PipelineError(LINK_BROKEN.format(reason=reason or f"error {response.status_code}"))
        raise PipelineError(f"Slack didn't accept the alert ({reason or f'error {response.status_code}'}). "
                            "The next run will try again.")


def configured_sender() -> SlackSender | None:
    """The Slack sender, or None if SLACK_WEBHOOK_URL isn't set up (then alerts stay off)."""
    load_dotenv()
    url = os.environ.get(WEBHOOK_ENV, "").strip()
    return SlackSender(url) if url.startswith(WEBHOOK_PREFIX) else None
