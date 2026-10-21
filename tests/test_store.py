"""Sheet-backed settings and run history, against an in-memory fake sheet. Google is never contacted."""

from datetime import UTC, date, datetime, timedelta

import pytest

from pipeline import store as store_module
from pipeline.errors import PipelineError
from pipeline.settings import SettingsInvalid, load_defaults, parse_settings
from pipeline.store import (
    DEFAULTS_AUTHOR,
    RUNS_TAB,
    SETTINGS_TAB,
    STALE_MESSAGE,
    SettingsConflict,
    Store,
)

OWNER = "owner@joinswc.org"


def custom_settings():
    return parse_settings(
        {
            "metrics": {"ga4": ["sessions"], "search_console": ["clicks", "ctr"]},
            "alert_thresholds": {"clicks": {"drop_pct": 40}},
            "alert_recipients": [OWNER],
        }
    )


# --- settings ---------------------------------------------------------------

def test_first_read_seeds_tbd_defaults_and_protects_tab(store, spreadsheet):
    record = store.read_settings()

    assert record.settings == load_defaults()
    assert record.updated_by == DEFAULTS_AUTHOR
    assert SETTINGS_TAB in spreadsheet.worksheets
    protected = spreadsheet.batch_requests[0]["requests"][0]["addProtectedRange"]["protectedRange"]
    assert protected["editors"]["users"] == ["pipeline@example.iam.gserviceaccount.com"]


def test_write_then_read_round_trips(store):
    saved = store.write_settings(custom_settings(), OWNER)
    record = store.read_settings()

    assert record.settings == custom_settings()
    assert record.version == saved.version
    assert record.updated_by == OWNER


def test_write_with_current_version_succeeds(store):
    version = store.read_settings().version
    store.write_settings(custom_settings(), OWNER, expected_version=version)
    assert store.read_settings().settings == custom_settings()


def test_write_with_stale_version_is_refused(store):
    stale = store.read_settings().version
    store.write_settings(custom_settings(), "someone-else@joinswc.org")

    with pytest.raises(SettingsConflict, match="Someone else changed the settings"):
        store.write_settings(load_defaults(), OWNER, expected_version=stale)
    assert store.read_settings().updated_by == "someone-else@joinswc.org"


def test_hand_edited_unreadable_value_is_explained(store, spreadsheet):
    store.read_settings()
    tab = spreadsheet.worksheets[SETTINGS_TAB]
    row = next(row for row in tab.rows if row[0] == "alert_recipients")
    row[1] = "owner@joinswc.org"  # typed in by hand, not JSON

    with pytest.raises(SettingsInvalid, match="Alert recipients: the value in the _settings tab"):
        store.read_settings()


def test_hand_edited_rule_breaking_value_is_explained(store, spreadsheet):
    store.read_settings()
    tab = spreadsheet.worksheets[SETTINGS_TAB]
    row = next(row for row in tab.rows if row[0] == "alert_recipients")
    row[1] = '["not-an-email"]'

    with pytest.raises(SettingsInvalid, match="'not-an-email' isn't a valid email address"):
        store.read_settings()


# --- runs -------------------------------------------------------------------

def test_run_lifecycle(store):
    run = store.start_run(date(2026, 10, 14), date(2026, 10, 20), "manual", OWNER)
    assert run.status == "running"
    assert store.current_run().id == run.id

    finished = store.finish_run(run.id, "success", 312, "All good.")
    assert finished.finished_at is not None

    [listed] = store.list_runs()
    assert listed.status == "success"
    assert listed.rows_written == 312
    assert listed.start_date == date(2026, 10, 14)
    assert listed.triggered_by == OWNER
    assert store.current_run() is None


def test_runs_listed_newest_first_and_limited(store, monkeypatch):
    base = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)
    ids = []
    for day in range(3):
        monkeypatch.setattr(store_module, "_now", lambda day=day: base + timedelta(days=day))
        ids.append(store.start_run(date(2026, 9, 1), date(2026, 9, 7), "scheduled", "scheduler").id)

    later = base + timedelta(days=3)
    assert [run.id for run in store.list_runs(now=later)] == list(reversed(ids))
    assert len(store.list_runs(limit=2, now=later)) == 2


def test_run_stuck_for_hours_counts_as_failed(store):
    run = store.start_run(date(2026, 10, 14), date(2026, 10, 20), "scheduled", "scheduler")
    three_hours_later = run.started_at + timedelta(hours=3)

    [listed] = store.list_runs(now=three_hours_later)
    assert listed.status == "failed"
    assert listed.message == STALE_MESSAGE
    assert store.current_run(now=three_hours_later) is None


def test_mangled_run_row_is_skipped(store, spreadsheet):
    store.start_run(date(2026, 10, 14), date(2026, 10, 20), "scheduled", "scheduler")
    spreadsheet.worksheets[RUNS_TAB].rows.append(["abc", "not a date"])

    assert len(store.list_runs()) == 1


def test_finishing_unknown_run_is_explained(store):
    with pytest.raises(PipelineError, match="Couldn't find run"):
        store.finish_run("missing", "success", 0, "")


def test_open_without_spreadsheet_id_is_explained(monkeypatch):
    monkeypatch.setattr(store_module, "load_dotenv", lambda: None)
    monkeypatch.delenv("SPREADSHEET_ID", raising=False)

    with pytest.raises(PipelineError, match="SPREADSHEET_ID is missing"):
        Store.open()
