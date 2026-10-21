"""Date range rules and the run stub, using the fake sheet. Google is never contacted."""

from datetime import date
from types import SimpleNamespace

import pytest
from googleapiclient.errors import HttpError

from pipeline import runner
from pipeline.errors import PipelineError
from pipeline.runner import (
    InvalidDateRange,
    RunAlreadyInProgress,
    StepResult,
    resolve_range,
)
from pipeline.settings import load_defaults

TODAY = date(2026, 10, 21)


# --- date ranges ------------------------------------------------------------

def test_default_is_seven_days_ending_yesterday():
    assert resolve_range(None, None, TODAY) == (date(2026, 10, 14), date(2026, 10, 20))


def test_valid_range_passes_through():
    assert resolve_range(date(2026, 1, 1), date(2026, 1, 31), TODAY) == (date(2026, 1, 1), date(2026, 1, 31))


@pytest.mark.parametrize(
    "start, end, reason",
    [
        (date(2026, 10, 1), None, "both a start date and an end date"),
        (None, date(2026, 10, 1), "both a start date and an end date"),
        (date(2026, 10, 10), date(2026, 10, 1), "is after the end date"),
        (date(2026, 10, 1), TODAY, "yesterday (20 Oct 2026) at the latest"),
        (date(2025, 6, 20), date(2025, 7, 1), "can't be earlier than 21 Jun 2025"),
        (date(2025, 6, 30), date(2026, 7, 1), "That's 367 days"),
    ],
)
def test_invalid_ranges_are_explained(start, end, reason):
    with pytest.raises(InvalidDateRange, match=reason.replace("(", r"\(").replace(")", r"\)")):
        resolve_range(start, end, TODAY)


def test_limits_are_inclusive():
    # Exactly 366 days, and the earliest day Search Console still has, are both allowed.
    assert resolve_range(date(2025, 7, 1), date(2026, 7, 1), TODAY)
    assert resolve_range(date(2025, 6, 21), date(2025, 6, 21), TODAY)


def test_months_before_handles_short_months():
    assert runner._months_before(date(2026, 3, 31), 1) == date(2026, 2, 28)


# --- running ----------------------------------------------------------------

def test_stub_run_succeeds_and_is_recorded(store):
    finished = runner.run(store=store, today=TODAY)

    assert finished.status == "success"
    assert finished.rows_written == 0
    assert "nothing was written" in finished.message
    assert (finished.start_date, finished.end_date) == (date(2026, 10, 14), date(2026, 10, 20))
    assert store.list_runs()[0].id == finished.id


def test_steps_receive_dates_and_settings(store):
    seen = {}

    def steps(start, end, settings):
        seen.update(start=start, end=end, settings=settings)
        return StepResult(42, "Pulled 42 rows.")

    finished = runner.run(date(2026, 9, 1), date(2026, 9, 30), trigger="manual",
                          triggered_by="owner@joinswc.org", store=store, steps=steps, today=TODAY)

    assert seen == {"start": date(2026, 9, 1), "end": date(2026, 9, 30), "settings": load_defaults()}
    assert (finished.rows_written, finished.message, finished.trigger) == (42, "Pulled 42 rows.", "manual")


def test_google_failure_is_recorded_in_plain_english(store):
    def steps(*_):
        raise HttpError(SimpleNamespace(status=403, reason=""), b"{}")

    finished = runner.run(store=store, steps=steps, today=TODAY)

    assert finished.status == "failed"
    assert "hasn't been added" in finished.message
    assert "Traceback" not in finished.message


def test_pipeline_error_message_is_kept(store):
    def steps(*_):
        raise PipelineError("The GA4 property ID is missing.")

    assert runner.run(store=store, steps=steps, today=TODAY).message == "The GA4 property ID is missing."


def test_refuses_to_start_while_another_run_is_going(store):
    store.start_run(date(2026, 10, 14), date(2026, 10, 20), "scheduled", "scheduler")

    with pytest.raises(RunAlreadyInProgress):
        runner.run(store=store, today=TODAY)
    assert len(store.list_runs()) == 1


def test_bad_dates_are_rejected_before_anything_is_recorded(store):
    with pytest.raises(InvalidDateRange):
        runner.run(date(2026, 10, 1), None, store=store, today=TODAY)
    assert store.list_runs() == []


# --- command line (what the Cloud Run Job calls) ----------------------------

def test_command_line_success(store, monkeypatch, capsys):
    monkeypatch.setattr(runner.Store, "open", classmethod(lambda cls: store))

    runner.main([])

    assert "success: Test run only" in capsys.readouterr().out


def test_command_line_failure_is_plain_and_exits_nonzero(store, monkeypatch, capsys):
    monkeypatch.setattr(runner.Store, "open", classmethod(lambda cls: store))

    with pytest.raises(SystemExit) as exit_:
        runner.main(["--start", "2026-10-01"])

    assert exit_.value.code == 1
    assert "The run didn't start. Please give both" in capsys.readouterr().out
