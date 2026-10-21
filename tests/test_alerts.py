"""Week-over-week drop alerts. Nothing is ever really emailed; the sender is fake."""

from datetime import UTC, date, datetime, timedelta

import pytest

from pipeline import alerts, load, mail
from pipeline.pull import pull_and_load
from pipeline.settings import parse_settings
from pipeline.store import ALERTS_TAB

NOW = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)
NEWEST = date(2026, 10, 20)
REAL_RECIPIENTS = ["owner@joinswc.org", "marisol@starrwellnesscollective.org"]


def settings(thresholds=None, recipients=REAL_RECIPIENTS, ga4=("sessions",), search_console=("clicks", "ctr")):
    return parse_settings(
        {
            "metrics": {"ga4": list(ga4), "search_console": list(search_console)},
            "alert_thresholds": thresholds if thresholds is not None else {"sessions": {"drop_pct": 30}},
            "alert_recipients": recipients,
        }
    )


def table(metric, earlier_daily, recent_daily, newest=NEWEST):
    """Two weeks of rows: 7 days at `earlier_daily`, then 7 at `recent_daily`, ending on `newest`."""
    rows = [["date", metric, "updated_at"]]
    for n in range(13, -1, -1):
        day = newest - timedelta(days=n)
        rows.append([day.isoformat(), earlier_daily if n >= 7 else recent_daily, "x"])
    return rows


class FakeSender:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    def send(self, recipients, subject, body):
        if self.fail:
            raise OSError("mail server unreachable")
        self.sent.append((recipients, subject, body))


def put(spreadsheet, tab, rows):
    worksheet = spreadsheet.add_worksheet(title=tab, rows=100, cols=10)
    worksheet.rows = [list(r) for r in rows]


# --- the weekly comparison ------------------------------------------------------------

def test_weekly_totals():
    assert alerts.weekly_totals(table("sessions", 10, 6), "sessions") == (NEWEST, 42, 70)


def test_needs_two_full_weeks_of_history():
    thirteen_days = table("sessions", 10, 6)
    del thirteen_days[1]  # drop the oldest day
    assert alerts.weekly_totals(thirteen_days, "sessions") is None
    assert alerts.weekly_totals([["date", "clicks", "updated_at"], ["2026-10-20", 3, "x"]], "clicks") is None


def test_missing_days_inside_the_two_weeks_count_as_zero():
    rows = table("clicks", 4, 4)
    del rows[10]  # a day in the latest week with no row: no clicks that day
    assert alerts.weekly_totals(rows, "clicks") == (NEWEST, 24, 28)


def test_week_ends_on_the_newest_day_the_source_reported():
    rows = table("clicks", 4, 4, newest=date(2026, 10, 18))  # Search Console is 2 days behind
    assert alerts.weekly_totals(rows, "clicks")[0] == date(2026, 10, 18)


def test_drop_past_the_alert_level_is_found():
    [drop] = alerts.find_drops(settings(), {"GA4": table("sessions", 10, 6)})
    assert (drop.metric, round(drop.drop_pct), drop.summary()) == ("sessions", 40, "Sessions down 40%")


def test_drop_below_the_alert_level_is_not():
    assert alerts.find_drops(settings(), {"GA4": table("sessions", 10, 8)}) == []  # 20% < 30%


def test_tiny_earlier_week_is_never_alerted():
    # 2 clicks to 0 is a "100%" drop, but the earlier week's total (14) is under 20.
    chosen = settings({"clicks": {"drop_pct": 50}})
    assert alerts.find_drops(chosen, {"Search Console": table("clicks", 2, 0)}) == []
    assert alerts.find_drops(chosen, {"Search Console": table("clicks", 3, 0)}) != []  # 21 is enough


def test_rates_are_not_checked_yet():
    chosen = settings({"ctr": {"drop_pct": 10}})
    assert alerts.find_drops(chosen, {"Search Console": table("ctr", 0.5, 0.1)}) == []


# --- sending -----------------------------------------------------------------------

@pytest.fixture
def dropping(spreadsheet):
    put(spreadsheet, load.GA4_TAB, table("sessions", 10, 6))


def test_sends_one_email_and_logs_it(store, spreadsheet, dropping):
    sender = FakeSender()

    outcome = alerts.check(settings(), store, NOW, lambda: sender)

    assert outcome == alerts.Outcome("Alert emailed to 2 people: Sessions down 40%.")
    [(to, subject, body)] = sender.sent
    assert to == REAL_RECIPIENTS
    assert subject == "Website numbers dropped: Sessions down 40%"
    assert "Sessions (Google Analytics): 70 → 42, down 40%" in body
    assert "Oct 14 – Oct 20 compared with Oct 7 – Oct 13. Alert level: 30%." in body
    log = spreadsheet.worksheets[ALERTS_TAB]
    assert log.rows[1][1:4] == ["GA4", "sessions", 40.0]


def test_same_metric_not_emailed_again_within_7_days(store, dropping):
    sender = FakeSender()
    alerts.check(settings(), store, NOW, lambda: sender)

    outcome = alerts.check(settings(), store, NOW + timedelta(days=6), lambda: sender)

    assert len(sender.sent) == 1
    assert outcome.message == "Alerts: still down (Sessions down 40%), already emailed in the last 7 days."


def test_emailed_again_after_7_days_if_still_down(store, dropping):
    sender = FakeSender()
    alerts.check(settings(), store, NOW, lambda: sender)
    alerts.check(settings(), store, NOW + timedelta(days=7), lambda: sender)
    assert len(sender.sent) == 2


def test_off_while_settings_are_placeholders(store, dropping):
    sender = FakeSender()

    outcome = alerts.check(settings(recipients=["alerts-tbd@example.com"]), store, NOW, lambda: sender)

    assert sender.sent == []
    assert outcome.message.startswith("Alerts are off until the placeholder settings are replaced")
    assert "Sessions down 40%" in outcome.message


def test_off_while_no_sender_is_set_up(store, dropping):
    outcome = alerts.check(settings(), store, NOW, lambda: None)
    assert outcome.message.startswith("Alerts are off because no sending mailbox is set up yet")


def test_failed_email_is_reported_and_not_logged_as_sent(store, spreadsheet, dropping):
    outcome = alerts.check(settings(), store, NOW, lambda: FakeSender(fail=True))

    assert not outcome.ok
    assert outcome.message.startswith("The alert email couldn't be sent.")
    assert ALERTS_TAB not in spreadsheet.worksheets  # so the next run tries again


def test_nothing_to_report(store):
    assert alerts.check(settings(), store, NOW, lambda: FakeSender()).message == (
        "Alerts: no numbers dropped past their alert level."
    )


# --- as part of a run ----------------------------------------------------------------

def test_run_continues_and_fails_clearly_if_the_email_cannot_be_sent(store, spreadsheet, dropping):
    result = pull_and_load(
        NEWEST, NEWEST, settings(), store,
        ga4=lambda *_: {}, search_console=lambda *_: {},
        sender_for=lambda: FakeSender(fail=True), now=NOW,
    )
    assert not result.ok
    assert result.message.startswith("The alert email couldn't be sent.")
    assert "GA4: 0 days updated." in result.message


def test_real_run_step_sends_nothing_until_the_mailbox_is_set_up(store, dropping, monkeypatch):
    monkeypatch.setattr(mail, "load_dotenv", lambda: None)
    monkeypatch.delenv(mail.REFRESH_TOKEN_ENV, raising=False)
    result = pull_and_load(NEWEST, NEWEST, settings(), store, ga4=lambda *_: {}, search_console=lambda *_: {}, now=NOW)
    assert result.ok and "no sending mailbox is set up yet" in result.message
