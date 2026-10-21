"""The real run step: pull GA4 and Search Console for the chosen days, write them
to the sheet, then check for drops worth an alert (pipeline/alerts.py).

Each source is pulled and written on its own, so if one fails the other is
still updated, and the run's message says exactly which one failed and why.
"""

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime

from pipeline import alerts, extract, load
from pipeline.errors import explain_error
from pipeline.runner import StepResult
from pipeline.settings import Settings
from pipeline.store import Store

log = logging.getLogger(__name__)

Fetch = Callable[[date, date, list[str]], dict[str, dict]]


def _plural(count: int) -> str:
    return f"{count} day" if count == 1 else f"{count} days"


def pull_and_load(
    start: date,
    end: date,
    settings: Settings,
    store: Store,
    *,
    ga4: Fetch = extract.fetch_ga4,
    search_console: Fetch = extract.fetch_search_console,
    sender_for: Callable[[], alerts.Sender | None] = alerts.no_sender,
    now: datetime | None = None,
) -> StepResult:
    now = now or datetime.now(UTC)
    wanted_days = (end - start).days + 1
    written = 0
    notes: list[str] = []
    problems: list[str] = []

    for label, tab, fetch, metrics in (
        ("GA4", load.GA4_TAB, ga4, list(settings.metrics.ga4)),
        ("Search Console", load.SEARCH_CONSOLE_TAB, search_console, list(settings.metrics.search_console)),
    ):
        try:
            days = load.write_daily(store, tab, fetch(start, end, metrics), metrics, now)
        except Exception as error:
            log.exception("%s step failed", label)
            problems.append(f"{label} wasn't updated. {explain_error(error, label)}")
            continue
        written += days
        note = f"{label}: {_plural(days)} updated."
        if days < wanted_days:
            note += f" Google hadn't reported the other {_plural(wanted_days - days)} yet; later runs fill them in."
        notes.append(note)

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
