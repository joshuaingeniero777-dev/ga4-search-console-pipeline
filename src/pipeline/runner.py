"""Run the pipeline once, recording the run and its outcome in the run history.

This is what the Cloud Run Job executes, both on schedule and for "Run now":

    python -m pipeline.runner                                  # last 7 days
    python -m pipeline.runner --start 2026-01-01 --end 2026-01-31 --trigger manual --triggered-by someone@joinswc.org

The real step is pipeline.pull.pull_and_load: GA4 and Search Console into the
sheet. `not_built_yet` is a stand-in that writes nothing; the tests and the
pretend-sheet dev server (scripts/dev_api.py) use it so they never reach Google.
"""

import argparse
import calendar
import logging
from collections.abc import Callable
from datetime import date, timedelta
from typing import NamedTuple

from pipeline import schedule
from pipeline.errors import PipelineError, explain_error
from pipeline.settings import Settings
from pipeline.store import Run, Store

log = logging.getLogger(__name__)

DEFAULT_DAYS = 7  # rolling window, because Search Console revises recent days (decision 3)
MAX_RANGE_DAYS = 366  # decision 16
SEARCH_CONSOLE_HISTORY_MONTHS = 16  # Google keeps no Search Console data older than this


class InvalidDateRange(PipelineError):
    pass


class RunAlreadyInProgress(PipelineError):
    pass


class StepResult(NamedTuple):
    rows_written: int
    message: str
    ok: bool = True  # False: something didn't work; `message` says what, and the run counts as failed


Steps = Callable[[date, date, Settings, Store], StepResult]


def not_built_yet(start: date, end: date, settings: Settings, store: Store) -> StepResult:
    return StepResult(0, "Test run only: nothing was pulled or written.")


def _show(day: date) -> str:
    return f"{day.day} {day:%b %Y}"


def _months_before(day: date, months: int) -> date:
    year, month_index = divmod(day.year * 12 + day.month - 1 - months, 12)
    month = month_index + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def default_range(today: date) -> tuple[date, date]:
    """The DEFAULT_DAYS full days ending yesterday."""
    end = today - timedelta(days=1)
    return end - timedelta(days=DEFAULT_DAYS - 1), end


def resolve_range(start: date | None, end: date | None, today: date) -> tuple[date, date]:
    """Fill in the default window, or check a requested one. Raises InvalidDateRange with a plain reason."""
    if start is None and end is None:
        return default_range(today)
    if start is None or end is None:
        raise InvalidDateRange(
            f"Please give both a start date and an end date, or neither to re-pull the last {DEFAULT_DAYS} days."
        )

    yesterday = today - timedelta(days=1)
    earliest = _months_before(today, SEARCH_CONSOLE_HISTORY_MONTHS)
    days = (end - start).days + 1
    if start > end:
        raise InvalidDateRange(f"The start date ({_show(start)}) is after the end date ({_show(end)}).")
    if end > yesterday:
        raise InvalidDateRange(
            f"The end date can be yesterday ({_show(yesterday)}) at the latest, because today's numbers aren't complete yet."
        )
    if start < earliest:
        raise InvalidDateRange(
            f"The start date can't be earlier than {_show(earliest)}. "
            f"Google only keeps {SEARCH_CONSOLE_HISTORY_MONTHS} months of Search Console data."
        )
    if days > MAX_RANGE_DAYS:
        raise InvalidDateRange(
            f"That's {days} days. One re-pull can cover at most {MAX_RANGE_DAYS} days, so please split it up."
        )
    return start, end


def run(
    start: date | None = None,
    end: date | None = None,
    *,
    trigger: str = "scheduled",
    triggered_by: str = "scheduler",
    store: Store | None = None,
    steps: Steps | None = None,
    today: date | None = None,
    run_id: str | None = None,
) -> Run:
    """Run once and return the finished run. Bad dates or a run already going raise before anything is recorded.

    Pass `run_id` when the run was already recorded (the API does this for "Run now",
    so a second click sees it as running straight away). `steps` defaults to the real
    pull (pipeline.pull.pull_and_load).
    """
    if steps is None:
        from pipeline.pull import (
            pull_and_load,  # here, not at the top: pull imports this module
        )

        steps = pull_and_load
    start, end = resolve_range(start, end, today or schedule.today())
    store = store or Store.open()
    if run_id is None:
        if store.current_run() is not None:
            raise RunAlreadyInProgress("A run is already in progress. Wait for it to finish, then try again.")
        run_id = store.start_run(start, end, trigger, triggered_by).id

    try:
        settings = store.read_settings().settings
        result = steps(start, end, settings, store)
    except Exception as error:
        # The full error goes to the server log; the run history gets the plain-English version.
        log.exception("Run %s failed", run_id)
        return store.finish_run(run_id, "failed", None, explain_error(error, "Google"))
    return store.finish_run(run_id, "success" if result.ok else "failed", result.rows_written, result.message)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the pipeline once.")
    parser.add_argument("--start", type=date.fromisoformat, help="first day, YYYY-MM-DD")
    parser.add_argument("--end", type=date.fromisoformat, help="last day, YYYY-MM-DD")
    parser.add_argument("--trigger", choices=["scheduled", "manual"], default="scheduled")
    parser.add_argument("--triggered-by", default="scheduler")
    parser.add_argument("--run-id", help="a run already recorded in the run history")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)

    try:
        finished = run(
            args.start, args.end, trigger=args.trigger, triggered_by=args.triggered_by, run_id=args.run_id
        )
    # Any failure at all becomes a plain-English message, never a stack trace.
    except Exception as error:  # noqa: BLE001
        print(f"The run didn't start. {explain_error(error, 'Google')}")
        raise SystemExit(1)

    print(f"Run {finished.id} {finished.status}: {finished.message}")
    if finished.status != "success":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
