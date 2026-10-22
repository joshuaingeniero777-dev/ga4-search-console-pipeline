"""The read-only health check. Google is faked, and the check must never write anything."""

from datetime import date

from pipeline.store import RUNS_TAB, SETTINGS_TAB, Store
from scripts import health_check
from scripts.health_check import Check


def read_only(spreadsheet):
    return Store(spreadsheet, "pipeline@example.iam.gserviceaccount.com", read_only=True)


def test_a_fresh_sheet_is_reported_not_created(spreadsheet):
    checks = health_check.check_sheet(read_only(spreadsheet), "Master")

    assert spreadsheet.worksheets == {}  # nothing created
    assert spreadsheet.batch_requests == []  # nothing locked
    settings = next(c for c in checks if c.name == "Settings")
    assert not settings.ok and "doesn't exist yet" in settings.detail
    assert next(c for c in checks if c.name == "Last run").detail == "The pipeline hasn't run yet."


def test_unlocked_tab_is_reported_and_left_alone(store, spreadsheet):
    store.read_settings()  # a normal (writing) store sets things up, locked
    store.start_run(date(2026, 10, 14), date(2026, 10, 20), "scheduled", "scheduler")
    spreadsheet.protections.clear()  # someone removed the locks
    requests_before = len(spreadsheet.batch_requests)

    checks = health_check.check_sheet(read_only(spreadsheet), "Master")

    locked = next(c for c in checks if c.name == "Locked tabs")
    assert not locked.ok and SETTINGS_TAB in locked.detail and RUNS_TAB in locked.detail
    assert len(spreadsheet.batch_requests) == requests_before  # didn't re-lock


def test_healthy_sheet(store, spreadsheet):
    store.read_settings()
    run = store.start_run(date(2026, 10, 14), date(2026, 10, 20), "scheduled", "scheduler")
    store.finish_run(run.id, "success", 12, "GA4: 7 days updated.")

    checks = health_check.check_sheet(read_only(spreadsheet), "Master")

    assert all(c.ok for c in checks), checks
    assert "GA4: 7 days updated." in next(c for c in checks if c.name == "Last run").detail


def test_sources_reported_in_plain_english():
    def broken(*_):
        raise FileNotFoundError()

    checks = health_check.check_sources({"GA4": lambda *_: {"2026-10-20": {}}, "Search Console": broken})

    assert checks[0] == Check("GA4", True, "Can read it (1 of the last 7 days reported so far).")
    assert not checks[1].ok and "service-account.json wasn't found" in checks[1].detail


def test_slack_link_must_be_a_real_slack_link(monkeypatch):
    monkeypatch.setattr(health_check, "load_dotenv", lambda: None)
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://example.com/not-slack")
    assert not next(c for c in health_check.check_setup() if c.name == "Slack alerts").ok

    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T/B/x")
    assert next(c for c in health_check.check_setup() if c.name == "Slack alerts").ok


def test_report_counts_what_needs_attention():
    text = health_check.report([Check("A", True, "fine"), Check("B", False, "broken")])
    assert text.splitlines() == ["OK  A: fine", "NO  B: broken", "", "1 thing(s) need attention (marked NO)."]
