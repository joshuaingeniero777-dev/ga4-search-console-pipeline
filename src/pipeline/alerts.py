"""Week-over-week drop alerts (docs/decisions.md, decisions 21-24).

For each count metric with an alert level in Settings, add up the latest 7 days
and the 7 days before that. If the latest week is down by at least the alert
level, email the alert recipients. Daily numbers here are tiny (0-2 clicks a
day), so single days would cry wolf; weekly totals don't.

- The "latest 7 days" end on the newest day the source has reported. Search
  Console runs 2-3 days behind, so its weeks end a little earlier than GA4's.
  A day inside the two weeks with no row counts as zero.
- No alert unless the earlier week's total is at least MIN_EARLIER_TOTAL;
  going from 2 clicks to 0 is "100%" but means nothing.
- Only counts are checked (COUNT_METRICS); rates like click-through rate aren't yet.
- The same metric is emailed at most once per REPEAT_AFTER.
- Alerts are off, and only described in the run's message, while any setting
  is still a TBD placeholder or no sender is set up.
"""

import logging
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import NamedTuple, Protocol

from pipeline import load
from pipeline.errors import explain_error
from pipeline.settings import (
    COUNT_METRICS,
    METRIC_LABELS,
    Settings,
    placeholder_warnings,
)
from pipeline.store import Store

log = logging.getLogger(__name__)

WINDOW_DAYS = 7
MIN_EARLIER_TOTAL = 20
REPEAT_AFTER = timedelta(days=7)

# Which tab holds each source's daily numbers, and what to call the source in an email.
SOURCES = {
    "GA4": (load.GA4_TAB, "Google Analytics"),
    "Search Console": (load.SEARCH_CONSOLE_TAB, "Google Search Console"),
}


class Drop(NamedTuple):
    source: str
    metric: str
    alert_level: int
    recent_total: float
    earlier_total: float
    recent_end: date  # the latest week is the 7 days ending here; the earlier week is the 7 before

    @property
    def drop_pct(self) -> float:
        return (self.earlier_total - self.recent_total) / self.earlier_total * 100

    @property
    def label(self) -> str:
        return METRIC_LABELS.get(self.metric, self.metric)

    def summary(self) -> str:
        return f"{self.label} down {self.drop_pct:.0f}%"


class Sender(Protocol):
    def send(self, recipients: list[str], subject: str, body: str) -> None: ...


class Outcome(NamedTuple):
    message: str  # plain English, added to the run's message
    ok: bool = True


def weekly_totals(table: list[list], metric: str) -> tuple[date, float, float] | None:
    """(newest day, latest week's total, earlier week's total), or None without 14 days of history."""
    if not table or metric not in table[0]:
        return None
    header = [str(cell) for cell in table[0]]
    date_at, value_at = header.index(load.DATE_COLUMN), header.index(metric)

    values: dict[date, float] = {}
    for row in table[1:]:
        if len(row) <= max(date_at, value_at) or row[value_at] in ("", None):
            continue
        try:
            values[date.fromisoformat(str(row[date_at]))] = float(row[value_at])
        except ValueError:
            continue
    if not values:
        return None

    newest, oldest = max(values), min(values)
    first_needed = newest - timedelta(days=2 * WINDOW_DAYS - 1)
    if oldest > first_needed:
        return None  # this metric doesn't go back two full weeks yet

    def total(last: date) -> float:
        return sum(values.get(last - timedelta(days=n), 0.0) for n in range(WINDOW_DAYS))

    return newest, total(newest), total(newest - timedelta(days=WINDOW_DAYS))


def find_drops(settings: Settings, tables: dict[str, list[list]]) -> list[Drop]:
    chosen = {"GA4": settings.metrics.ga4, "Search Console": settings.metrics.search_console}
    drops = []
    for source, metrics in chosen.items():
        for metric in metrics:
            threshold = settings.alert_thresholds.get(metric)
            if threshold is None or metric not in COUNT_METRICS:
                continue
            totals = weekly_totals(tables.get(source, []), metric)
            if totals is None:
                continue
            newest, recent, earlier = totals
            if earlier < MIN_EARLIER_TOTAL:
                continue
            drop = Drop(source, metric, threshold.drop_pct, recent, earlier, newest)
            if drop.drop_pct >= threshold.drop_pct:
                drops.append(drop)
    return drops


def _days(last: date) -> str:
    first = last - timedelta(days=WINDOW_DAYS - 1)
    return f"{first:%b} {first.day} – {last:%b} {last.day}"


def _number(value: float) -> str:
    return f"{value:,.0f}"


def email(drops: list[Drop]) -> tuple[str, str]:
    """Subject and plain-text body. Written for someone who isn't technical."""
    subject = "Website numbers dropped: " + (
        drops[0].summary() if len(drops) == 1 else f"{len(drops)} numbers are down this week"
    )
    lines = [
        "Hi,",
        "",
        "The data pipeline compared the latest 7 days with the 7 days before, and these numbers dropped",
        "by more than the alert level you set:",
        "",
    ]
    for d in drops:
        earlier_end = d.recent_end - timedelta(days=WINDOW_DAYS)
        lines += [
            (
                f"- {d.label} ({SOURCES[d.source][1]}): {_number(d.earlier_total)} → {_number(d.recent_total)}, "
                f"down {d.drop_pct:.0f}%"
            ),
            f"  {_days(d.recent_end)} compared with {_days(earlier_end)}. Alert level: {d.alert_level}%.",
            "",
        ]
    lines += [
        "Small numbers can swing a lot from week to week, so this may be nothing to worry about.",
        "The day-by-day numbers are in the master Google Sheet (GA4 and Search Console tabs) and in Looker Studio.",
        "",
        "You won't get another email about the same number for 7 days.",
        "You're getting this because you're on the alert list. To change who gets alerts, or the alert",
        "levels, go to Settings in the pipeline's control panel.",
    ]
    return subject, "\n".join(lines)


def no_sender() -> Sender | None:
    """How alert emails are sent isn't decided yet (docs/ROADMAP.md, item 6), so nothing is sent."""
    return None


def check(
    settings: Settings,
    store: Store,
    now: datetime,
    sender_for: Callable[[], Sender | None],
) -> Outcome:
    """Look for drops and email the ones that are due. `sender_for` returns None when sending isn't set up."""
    tables = {source: load.read_daily(store, tab) for source, (tab, _) in SOURCES.items()}
    drops = find_drops(settings, tables)
    if not drops:
        return Outcome("Alerts: no numbers dropped past their alert level.")
    found = ", ".join(d.summary() for d in drops)

    if placeholder_warnings(settings):
        return Outcome(f"Alerts are off until the placeholder settings are replaced; they would have flagged: {found}.")
    sender = sender_for()
    if sender is None:
        return Outcome(f"Alerts are off because no sending mailbox is set up yet; they would have flagged: {found}.")

    last = store.last_alerts()
    due = [d for d in drops if now - last.get((d.source, d.metric), datetime.min.replace(tzinfo=now.tzinfo)) >= REPEAT_AFTER]
    if not due:
        return Outcome(f"Alerts: still down ({found}), already emailed in the last 7 days.")

    subject, body = email(due)
    recipients = list(settings.alert_recipients)
    try:
        sender.send(recipients, subject, body)
    except Exception as error:
        log.exception("Alert email failed")
        return Outcome(f"The alert email couldn't be sent. {explain_error(error, 'Gmail')}", ok=False)

    for d in due:
        store.record_alert(
            [now.isoformat(), d.source, d.metric, round(d.drop_pct, 1), d.recent_total, d.earlier_total,
             f"{_days(d.recent_end)} vs {_days(d.recent_end - timedelta(days=WINDOW_DAYS))}", ", ".join(recipients)]
        )
    people = "1 person" if len(recipients) == 1 else f"{len(recipients)} people"
    return Outcome(f"Alert emailed to {people}: {', '.join(d.summary() for d in due)}.")
