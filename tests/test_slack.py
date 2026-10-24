"""Posting alerts to Slack. Slack is faked; nothing is ever posted."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
import requests

from pipeline import alerts, load, slack
from pipeline.errors import PipelineError
from pipeline.settings import parse_settings

SECRET_LINK = "https://hooks.slack.com/services/T000/B000/very-secret-part"


def answer(status=200, text="ok"):
    return lambda *a, **k: SimpleNamespace(status_code=status, text=text)


def test_posts_the_alert_as_one_message():
    calls = []
    sender = slack.SlackSender(SECRET_LINK, post=lambda url, **k: calls.append((url, k)) or answer()())

    sender.send([], "Website numbers dropped: Sessions down 40%", "Hi,\n- Sessions: 70 → 42")

    [(url, kwargs)] = calls
    assert url == SECRET_LINK
    assert kwargs["json"] == {"text": "*Website numbers dropped: Sessions down 40%*\n\nHi,\n- Sessions: 70 → 42"}
    assert kwargs["timeout"] == slack.TIMEOUT_SECONDS


def test_unreachable_slack_is_explained_without_the_link():
    def down(url, **k):
        raise requests.ConnectionError(f"Max retries exceeded with url: {url}")

    with pytest.raises(PipelineError) as caught:
        slack.SlackSender(SECRET_LINK, post=down).send([], "s", "b")

    assert str(caught.value) == slack.UNREACHABLE
    assert caught.value.__cause__ is None and caught.value.__suppress_context__


@pytest.mark.parametrize("status, reason", [(404, "no_service"), (404, "channel_not_found"), (403, "invalid_token"), (410, "channel_is_archived")])
def test_broken_link_says_a_new_one_is_needed(status, reason):
    with pytest.raises(PipelineError, match="make a new Slack link") as caught:
        slack.SlackSender(SECRET_LINK, post=answer(status, reason)).send([], "s", "b")
    assert reason in str(caught.value)


def test_passing_hiccup_says_it_will_retry():
    with pytest.raises(PipelineError, match="The next run will try again"):
        slack.SlackSender(SECRET_LINK, post=answer(500, "")).send([], "s", "b")


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setattr(slack, "load_dotenv", lambda: None)
    return monkeypatch


def test_sender_is_ready_with_a_slack_link(env):
    env.setenv(slack.WEBHOOK_ENV, SECRET_LINK)
    assert isinstance(slack.configured_sender(), slack.SlackSender)


@pytest.mark.parametrize("value", [None, "", "https://example.com/not-slack", "hooks.slack.com/services/x"])
def test_no_sender_without_a_real_slack_link(env, value):
    if value is None:
        env.delenv(slack.WEBHOOK_ENV, raising=False)
    else:
        env.setenv(slack.WEBHOOK_ENV, value)
    assert slack.configured_sender() is None


def test_a_failed_post_never_puts_the_link_in_the_run_message(store, spreadsheet, caplog):
    worksheet = spreadsheet.add_worksheet(title=load.GA4_TAB, rows=100, cols=5)
    worksheet.rows = [["date", "sessions", "updated_at"]] + [
        [f"2026-10-{d:02d}", 10 if d <= 13 else 6, "x"] for d in range(7, 21)
    ]

    def down(url, **k):
        raise requests.ConnectionError(f"Max retries exceeded with url: {url}")

    chosen = parse_settings({"metrics": {"ga4": ["sessions"], "search_console": ["clicks"]},
                             "alert_thresholds": {"sessions": {"drop_pct": 25}}})
    outcome = alerts.check(chosen, store, datetime(2026, 10, 21, tzinfo=UTC),
                           lambda: slack.SlackSender(SECRET_LINK, post=down))

    assert not outcome.ok and outcome.message == f"The alert couldn't be sent. {slack.UNREACHABLE}"
    assert "very-secret-part" not in outcome.message
    assert "very-secret-part" not in caplog.text
