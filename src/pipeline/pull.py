"""The real run step: pull GA4 and Search Console for the chosen days, write them
to the sheet, then check for drops worth an alert (pipeline/alerts.py).

Each source is pulled and written on its own, so if one fails the other is
still updated, and the run's message says exactly which one failed and why.
"""

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime

from pipeline import alerts, extract, load, slack
from pipeline.errors import explain_error
from pipeline.runner import StepResult
from pipeline.settings import Settings
from pipeline.store import Store

log = logging.getLogger(__name__)

Fetch = Callable[[date, date, list[str]], dict[str, dict]]


def _plural(count: int) -> str:
    return f"{count} day" if count == 1 else f"{count} days"


def _describe(label: str, fresh: dict, start: date, end: date) -> str:
    """What was updated, and why any days are missing, in plain English.

    Days after the newest one Google reported haven't been reported yet (later runs
    fill them in). Days before it that are missing have no record at all, e.g. GA4
    wasn't recording; they're left blank, never written as 0 (decision 29).
    """
    note = f"{label}: {_plural(len(fresh))} updated."
    if not fresh:
        return note + " Google had nothing for these days."
    reported = {date.fromisoformat(day) for day in fresh}
    newest = max(reported)
    no_record = (newest - start).days + 1 - len({d for d in reported if d >= start})
    not_yet = (end - newest).days
    if no_record:
        note += f" {_plural(no_record).capitalize()} had no {label} record and stay blank."
    if not_yet:
        note += f" Google hasn't reported the newest {_plural(not_yet)} yet; later runs fill them in."
    return note


def pull_and_load(
    start: date,
    end: date,
    settings: Settings,
    store: Store,
    *,
    ga4: Fetch = extract.fetch_ga4,
    search_console: Fetch = extract.fetch_search_console,
    sender_for: Callable[[], alerts.Sender | None] = slack.configured_sender,
    now: datetime | None = None,
) -> StepResult:
    now = now or datetime.now(UTC)
    written = 0
    notes: list[str] = []
    problems: list[str] = []

    for label, tab, fetch, metrics in (
        ("GA4", load.GA4_TAB, ga4, list(settings.metrics.ga4)),
        ("Search Console", load.SEARCH_CONSOLE_TAB, search_console, list(settings.metrics.search_console)),
    ):
        try:
            fresh = fetch(start, end, metrics)
            days = load.write_daily(store, tab, fresh, metrics, now)
        except Exception as error:
            log.exception("%s step failed", label)
            problems.append(f"{label} wasn't updated. {explain_error(error, label)}")
            continue
        written += days
        notes.append(_describe(label, fresh, start, end))

    # Alerts look at everything in the tabs, so they still run if one source failed today.
    try:
        alert = alerts.check(settings, store, now, sender_for)
    except Exception as error:
        log.exception("Alert check failed")
        alert = alerts.Outcome(f"Alerts couldn't be checked. {explain_error(error, 'Google Sheets')}", ok=False)
    notes.append(alert.message)
    if not alert.ok:
        problems.append(notes.pop())

    return StepResult(written, " ".join(problems + notes), ok=not problems)
