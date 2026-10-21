"""Pulling daily numbers and writing them to the GA4 and Search Console tabs. Google is faked."""

from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from googleapiclient.errors import HttpError

from pipeline import extract, load, runner
from pipeline.errors import PipelineError
from pipeline.pull import pull_and_load
from pipeline.settings import parse_settings
from pipeline.store import RUNS_TAB

START, END = date(2026, 10, 14), date(2026, 10, 20)
NOW = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)
STAMP = "2026-10-21 10:00 UTC"


def settings(ga4=("sessions", "totalUsers"), search_console=("clicks", "ctr")):
    return parse_settings(
        {
            "metrics": {"ga4": list(ga4), "search_console": list(search_console)},
            "alert_thresholds": {},
            "alert_recipients": ["owner@joinswc.org"],
        }
    )


# --- extract ---------------------------------------------------------------------

class FakeGA4:
    def __init__(self, rows):
        self.rows = rows
        self.request = None

    def run_report(self, request):
        self.request = request
        header = lambda name, kind: SimpleNamespace(name=name, type_=SimpleNamespace(name=kind))
        return SimpleNamespace(
            metric_headers=[header("sessions", "TYPE_INTEGER"), header("engagementRate", "TYPE_FLOAT")],
            rows=[
                SimpleNamespace(
                    dimension_values=[SimpleNamespace(value=day)],
                    metric_values=[SimpleNamespace(value=v) for v in values],
                )
                for day, values in self.rows
            ],
        )


def test_ga4_one_row_per_day_with_proper_numbers():
    client = FakeGA4([("20261014", ["120", "0.612345678"]), ("20261015", ["98", "0.5"])])

    daily = extract.ga4_daily(client, "123456789", ["sessions", "engagementRate"], START, END)

    assert daily == {
        "2026-10-14": {"sessions": 120, "engagementRate": 0.6123},
        "2026-10-15": {"sessions": 98, "engagementRate": 0.5},
    }
    assert client.request.property == "properties/123456789"
    assert [d.name for d in client.request.dimensions] == ["date"]
    assert (client.request.date_ranges[0].start_date, client.request.date_ranges[0].end_date) == (
        "2026-10-14", "2026-10-20",
    )


class FakeSearchConsole:
    def __init__(self, rows):
        self.rows = rows
        self.call = None

    def searchanalytics(self):
        return self

    def query(self, siteUrl, body):
        self.call = (siteUrl, body)
        return self

    def execute(self):
        return {"rows": self.rows} if self.rows else {}


def test_search_console_one_row_per_day_only_chosen_metrics():
    service = FakeSearchConsole(
        [{"keys": ["2026-10-14"], "clicks": 31.0, "impressions": 900.0, "ctr": 0.0344444, "position": 12.71}]
    )

    daily = extract.search_console_daily(service, "sc-domain:joinswc.org", ["clicks", "ctr"], START, END)

    assert daily == {"2026-10-14": {"clicks": 31, "ctr": 0.0344}}
    site, body = service.call
    assert site == "sc-domain:joinswc.org"
    assert body["dimensions"] == ["date"] and body["startDate"] == "2026-10-14" and body["endDate"] == "2026-10-20"


def test_no_rows_means_no_days_not_zeros():
    assert extract.search_console_daily(FakeSearchConsole([]), "s", ["clicks"], START, END) == {}


def test_missing_ids_are_explained(monkeypatch):
    monkeypatch.setattr(extract, "load_dotenv", lambda: None)
    monkeypatch.delenv("GA4_PROPERTY_ID", raising=False)
    with pytest.raises(PipelineError, match="GA4_PROPERTY_ID is missing from .env"):
        extract.ga4_property_id()


# --- merging into a tab -------------------------------------------------------------

def test_merge_into_empty_tab():
    table = load.merge([], {"2026-10-15": {"clicks": 5}, "2026-10-14": {"clicks": 3}}, ["clicks"], "T", STAMP)
    assert table == [
        ["date", "clicks", "updated_at"],
        ["2026-10-14", 3, STAMP],
        ["2026-10-15", 5, STAMP],
    ]


def test_repulled_day_replaces_its_row_instead_of_duplicating():
    existing = [["date", "clicks", "updated_at"], ["2026-10-14", 3, "old"], ["2026-10-15", 5, "old"]]
    table = load.merge(existing, {"2026-10-15": {"clicks": 7}}, ["clicks"], "T", STAMP)
    assert table[1:] == [["2026-10-14", 3, "old"], ["2026-10-15", 7, STAMP]]


def test_new_metric_adds_a_column_and_dropped_metric_keeps_its_history():
    existing = [["date", "clicks", "updated_at"], ["2026-10-14", 3, "old"]]
    table = load.merge(existing, {"2026-10-15": {"impressions": 90}}, ["impressions"], "T", STAMP)
    assert table == [
        ["date", "clicks", "impressions", "updated_at"],
        ["2026-10-14", 3, "", "old"],
        ["2026-10-15", "", 90, STAMP],
    ]


def test_unreadable_date_stops_instead_of_losing_the_row():
    existing = [["date", "clicks", "updated_at"], ["2026-10-14", 3, "x"], ["Oct 15", 5, "x"]]
    with pytest.raises(PipelineError, match=r"Row 3 of the T tab has a date the pipeline can't read \('Oct 15'\)"):
        load.merge(existing, {}, ["clicks"], "T", STAMP)


def test_blank_rows_are_ignored():
    existing = [["date", "clicks", "updated_at"], ["", "", ""], ["2026-10-14", 3, "x"]]
    assert load.merge(existing, {}, ["clicks"], "T", STAMP)[1:] == [["2026-10-14", 3, "x"]]


# --- the whole step ---------------------------------------------------------------

def fake_ga4(days):
    return lambda start, end, metrics: {d: {m: 10 for m in metrics} for d in days}


def fake_sc(days):
    return lambda start, end, metrics: {d: {m: 0.5 if m == "ctr" else 4 for m in metrics} for d in days}


WEEK = [f"2026-10-{d}" for d in range(14, 21)]


def test_both_tabs_written_one_row_per_day(store, spreadsheet):
    result = pull_and_load(START, END, settings(), store, ga4=fake_ga4(WEEK), search_console=fake_sc(WEEK[:5]), now=NOW)

    assert result.ok and result.rows_written == 12
    assert result.message == (
        "GA4: 7 days updated. "
        "Search Console: 5 days updated. Google hadn't reported the other 2 days yet; later runs fill them in. "
        "Alerts: no numbers dropped past their alert level."
    )
    ga4_tab = spreadsheet.worksheets[load.GA4_TAB]
    assert ga4_tab.rows[0] == ["date", "sessions", "totalUsers", "updated_at"]
    assert ga4_tab.rows[1] == ["2026-10-14", 10, 10, STAMP]
    assert len(ga4_tab.rows) == 8
    assert spreadsheet.worksheets[load.SEARCH_CONSOLE_TAB].rows[0] == ["date", "clicks", "ctr", "updated_at"]
    assert ga4_tab.formats == [("A2:A8", load.DATE_FORMAT)]


def test_data_tabs_are_locked_like_the_others(store, spreadsheet):
    pull_and_load(START, END, settings(), store, ga4=fake_ga4(WEEK), search_console=fake_sc(WEEK), now=NOW)

    locked = {p["range"]["sheetId"] for p in spreadsheet.protections}
    assert spreadsheet.worksheets[load.GA4_TAB].id in locked
    assert spreadsheet.worksheets[load.SEARCH_CONSOLE_TAB].id in locked


def test_running_twice_does_not_duplicate_days(store, spreadsheet):
    for _ in range(2):
        pull_and_load(START, END, settings(), store, ga4=fake_ga4(WEEK), search_console=fake_sc(WEEK), now=NOW)
    assert len(spreadsheet.worksheets[load.GA4_TAB].rows) == 8


def test_tab_grows_when_a_long_repull_needs_more_rows(store, spreadsheet):
    year = [date.fromordinal(START.toordinal() - n).isoformat() for n in range(300)]

    pull_and_load(START, END, settings(), store, ga4=fake_ga4(year), search_console=fake_sc([]), now=NOW)

    tab = spreadsheet.worksheets[load.GA4_TAB]
    assert len(tab.rows) == 301 and tab.row_count >= 301


def test_one_source_failing_still_updates_the_other_and_says_which(store, spreadsheet):
    def broken(*_):
        raise HttpError(SimpleNamespace(status=403, reason=""), b"{}")

    result = pull_and_load(START, END, settings(), store, ga4=fake_ga4(WEEK), search_console=broken, now=NOW)

    assert not result.ok and result.rows_written == 7
    assert result.message.startswith("Search Console wasn't updated. Google said no (403).")
    assert "GA4: 7 days updated." in result.message
    assert load.SEARCH_CONSOLE_TAB not in spreadsheet.worksheets


def test_runner_records_a_partly_failed_run_as_failed(store):
    def broken(*_):
        raise PipelineError("GSC_SITE_URL is missing from .env, so the pipeline doesn't know which site to read.")

    def steps(start, end, chosen, st):
        return pull_and_load(start, end, chosen, st, ga4=fake_ga4(WEEK), search_console=broken, now=NOW)

    finished = runner.run(START, END, store=store, steps=steps, today=date(2026, 10, 21))

    assert finished.status == "failed" and finished.rows_written == 7
    assert "GSC_SITE_URL is missing" in finished.message
    assert RUNS_TAB in store._spreadsheet.worksheets
