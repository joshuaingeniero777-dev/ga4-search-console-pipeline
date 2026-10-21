"""The five API endpoints, against the fake sheet. Sign-in is faked here; tests/test_api_auth.py covers it."""

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from api.auth import DEFAULT_PANEL_ORIGIN, PANEL_ORIGIN_ENV, current_user
from api.main import app
from api.routes import DISPATCH_FAILED, get_dispatcher, get_store
from pipeline import runner, schedule
from pipeline.errors import PipelineError
from pipeline.store import RUNS_HEADER, SETTINGS_TAB

OWNER = "owner@joinswc.org"


class FakeDispatcher:
    def __init__(self):
        self.dispatched = []
        self.fail = False

    def dispatch(self, run):
        if self.fail:
            raise OSError("couldn't start process")
        self.dispatched.append(run)


@pytest.fixture
def dispatcher():
    return FakeDispatcher()


@pytest.fixture
def client(store, dispatcher, monkeypatch):
    monkeypatch.delenv(PANEL_ORIGIN_ENV, raising=False)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_dispatcher] = lambda: dispatcher
    app.dependency_overrides[current_user] = lambda: OWNER
    # Browsers send Origin on saves and runs; the panel's is the default PANEL_ORIGIN.
    yield TestClient(app, headers={"Origin": DEFAULT_PANEL_ORIGIN})
    app.dependency_overrides.clear()


def valid_settings(**overrides):
    data = {
        "metrics": {"ga4": ["sessions"], "search_console": ["clicks"]},
        "alert_thresholds": {"sessions": {"drop_pct": 25}},
        "alert_recipients": [OWNER],
    }
    return {**data, **overrides}


def yesterday():
    return schedule.today().toordinal() - 1


# --- GET /status --------------------------------------------------------------

def test_status_before_any_run(client):
    body = client.get("/status").json()

    assert body["state"] == "never_run"
    assert body["message"] == "The pipeline hasn't run yet."
    assert body["last_run"] is None
    assert len(body["warnings"]) == 3  # metrics, thresholds, recipients still TBD
    next_run = datetime.fromisoformat(body["next_run_at"])
    assert (next_run.hour, next_run.minute) == (6, 0)
    assert next_run.utcoffset() == next_run.astimezone(schedule.TIMEZONE).utcoffset()


def test_status_after_successful_run(client, store):
    runner.run(store=store)

    body = client.get("/status").json()

    assert body["state"] == "ok"
    assert "worked" in body["message"] and "nothing was written" in body["message"]
    assert body["last_run"]["status"] == "success"


def test_status_after_failed_run(client, store):
    def steps(*_):
        raise PipelineError("The GA4 property ID is missing.")

    runner.run(store=store, steps=steps)

    body = client.get("/status").json()
    assert body["state"] == "failed"
    assert body["message"].endswith("failed. The GA4 property ID is missing.")


def test_status_while_running(client, store):
    store.start_run(date(2026, 10, 14), date(2026, 10, 20), "manual", OWNER)

    body = client.get("/status").json()
    assert body["state"] == "running"
    assert body["message"].startswith("A run is in progress (started ")


def test_status_reports_broken_settings(client, store, spreadsheet):
    store.read_settings()
    row = next(r for r in spreadsheet.worksheets[SETTINGS_TAB].rows if r[0] == "alert_recipients")
    row[1] = '["bob@"]'

    body = client.get("/status").json()
    assert body["state"] == "settings_invalid"
    assert "'bob@' isn't a valid email address" in body["message"]


def test_status_warns_when_a_tab_was_relocked(client, spreadsheet):
    tab = spreadsheet.add_worksheet(title=SETTINGS_TAB, rows=100, cols=4)
    tab.append_row(["key", "value", "updated_at", "updated_by"])  # made by hand, never locked

    warnings = client.get("/status").json()["warnings"]
    assert any("_settings tab in the sheet had been unlocked" in warning for warning in warnings)


# --- GET /runs ----------------------------------------------------------------

def test_runs_newest_first_with_limit(client, store):
    first = runner.run(store=store)
    second = runner.run(store=store)

    assert [run["id"] for run in client.get("/runs").json()["runs"]] == [second.id, first.id]
    assert len(client.get("/runs?limit=1").json()["runs"]) == 1


@pytest.mark.parametrize("limit", [0, 101, "lots"])
def test_runs_limit_out_of_range(client, limit):
    response = client.get(f"/runs?limit={limit}")
    assert response.status_code == 422
    assert response.json()["detail"].startswith("Limit: ")


# --- POST /runs ---------------------------------------------------------------

def test_run_now_with_default_dates(client, store, dispatcher):
    response = client.post("/runs")

    assert response.status_code == 202
    run = response.json()["run"]
    assert run["status"] == "running"
    assert run["trigger"] == "manual"
    assert run["triggered_by"] == OWNER
    assert date.fromisoformat(run["end_date"]).toordinal() == yesterday()
    assert [r.id for r in dispatcher.dispatched] == [run["id"]]
    assert store.current_run().id == run["id"]


def test_run_now_with_chosen_dates(client, dispatcher):
    response = client.post("/runs", json={"start_date": "2026-09-01", "end_date": "2026-09-30"})

    assert response.status_code == 202
    assert (dispatcher.dispatched[0].start_date, dispatcher.dispatched[0].end_date) == (
        date(2026, 9, 1), date(2026, 9, 30),
    )


@pytest.mark.parametrize(
    "body, reason",
    [
        ({"start_date": "2026-09-01"}, "Please give both a start date and an end date"),
        ({"start_date": "2026-09-30", "end_date": "2026-09-01"}, "is after the end date"),
        ({"start_date": "2020-01-01", "end_date": "2020-01-31"}, "can't be earlier than"),
        ({"start_date": "1 Sept", "end_date": "2026-09-30"}, "Start date: "),
        ({"start_date": "2026-09-01", "end_date": "2026-09-30", "extra": 1}, "isn't a recognised setting"),
    ],
)
def test_run_now_rejects_bad_requests(client, store, dispatcher, body, reason):
    response = client.post("/runs", json=body)

    assert response.status_code == 422
    assert reason in response.json()["detail"]
    assert store.list_runs() == [] and dispatcher.dispatched == []


def test_second_click_is_refused_while_running(client, dispatcher):
    assert client.post("/runs").status_code == 202

    response = client.post("/runs")
    assert response.status_code == 409
    assert response.json()["detail"].startswith("A run is already in progress")
    assert len(dispatcher.dispatched) == 1


def test_run_that_cannot_be_started_is_recorded_as_failed(client, store, dispatcher):
    dispatcher.fail = True

    response = client.post("/runs")

    assert response.status_code == 503
    assert response.json()["detail"] == DISPATCH_FAILED
    [run] = store.list_runs()
    assert (run.status, run.message) == ("failed", DISPATCH_FAILED)


def test_dispatched_run_finishes_the_recorded_row(client, store, dispatcher):
    # What the separate process does with the run the API recorded.
    client.post("/runs")
    recorded = dispatcher.dispatched[0]

    runner.run(recorded.start_date, recorded.end_date, store=store, run_id=recorded.id)

    [run] = store.list_runs()
    assert (run.id, run.status, run.triggered_by) == (recorded.id, "success", OWNER)


# --- GET and PUT /settings ------------------------------------------------------

def test_get_settings_seeds_tbd_defaults(client):
    body = client.get("/settings").json()

    assert body["settings"]["alert_recipients"] == ["alerts-tbd@example.com"]
    assert body["version"] and body["problem"] is None
    assert len(body["warnings"]) == 3
    options = body["options"]
    assert {"name": "sessions", "label": "Sessions"} in options["ga4"]
    assert (options["max_recipients"], options["min_drop_pct"], options["max_drop_pct"]) == (10, 1, 100)


def test_put_settings_saves_and_clears_warnings(client):
    version = client.get("/settings").json()["version"]

    response = client.put("/settings", json={"settings": valid_settings(), "version": version})

    assert response.status_code == 200
    body = response.json()
    assert body["updated_by"] == OWNER and body["version"] != version
    assert body["warnings"] == []
    assert client.get("/settings").json()["settings"] == valid_settings()


def test_put_settings_with_stale_version_is_refused(client):
    stale = client.get("/settings").json()["version"]
    client.put("/settings", json={"settings": valid_settings(), "version": stale})

    response = client.put("/settings", json={"settings": valid_settings(alert_recipients=["x@joinswc.org"]), "version": stale})

    assert response.status_code == 409
    assert response.json()["detail"] == "Someone else changed the settings. Reload and try again."


@pytest.mark.parametrize(
    "settings, message",
    [
        (valid_settings(alert_recipients=["bob@"]), "Alert recipients: 'bob@' isn't a valid email address."),
        (valid_settings(alert_thresholds={"sessions": {"drop_pct": 0}}), "Alert thresholds > sessions > drop %:"),
        (valid_settings(alert_thresholds={"impressions": {"drop_pct": 10}}), "isn't one of the metrics being pulled"),
    ],
)
def test_put_settings_explains_broken_rules(client, settings, message):
    version = client.get("/settings").json()["version"]

    response = client.put("/settings", json={"settings": settings, "version": version})

    assert response.status_code == 422
    assert message in response.json()["detail"]


def test_put_settings_needs_a_version(client):
    response = client.put("/settings", json={"settings": valid_settings()})
    assert response.status_code == 422
    assert response.json()["detail"].startswith("Version: ")


def test_broken_saved_settings_can_be_fixed_through_the_api(client, store, spreadsheet):
    store.read_settings()
    row = next(r for r in spreadsheet.worksheets[SETTINGS_TAB].rows if r[0] == "alert_recipients")
    row[1] = "not json"

    broken = client.get("/settings").json()
    assert broken["settings"] is None and "Alert recipients" in broken["problem"]

    response = client.put("/settings", json={"settings": valid_settings(), "version": broken["version"]})
    assert response.status_code == 200
    assert client.get("/status").json()["state"] != "settings_invalid"


# --- errors -------------------------------------------------------------------

def test_expected_problem_is_plain_english(client):
    def no_sheet():
        raise PipelineError("SPREADSHEET_ID is missing from .env, so the pipeline doesn't know which sheet to use.")

    app.dependency_overrides[get_store] = no_sheet
    response = client.get("/status")

    assert response.status_code == 503
    assert response.json() == {"detail": "SPREADSHEET_ID is missing from .env, so the pipeline doesn't know which sheet to use."}


def test_unexpected_error_hides_the_details(store):
    class Broken:
        def list_runs(self, **_):
            raise KeyError("internal detail")

    app.dependency_overrides[get_store] = lambda: Broken()
    app.dependency_overrides[current_user] = lambda: OWNER
    try:
        response = TestClient(app, raise_server_exceptions=False).get("/runs")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert "internal detail" not in response.text
    assert response.json()["detail"].startswith("Something went wrong on the server")


def test_runs_tab_columns_are_stable():
    # The API returns these fields; the panel depends on them.
    assert RUNS_HEADER[:4] == ["id", "started_at", "finished_at", "status"]
