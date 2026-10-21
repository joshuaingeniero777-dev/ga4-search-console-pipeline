"""When the pipeline runs on its own (docs/decisions.md, decision 14).

The actual trigger lives in the cloud scheduler's config. These values mirror
it so the control panel can say when the next run is; change both together.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/New_York")
RUN_TIME = time(6, 0)
CRON = "0 6 * * *"  # in TIMEZONE; for the cloud scheduler


def today() -> date:
    """Today's date in the business's timezone, not the server's (cloud servers run on UTC)."""
    return datetime.now(TIMEZONE).date()


def next_run_at(now: datetime) -> datetime:
    """The next scheduled run strictly after `now`, in the business's timezone."""
    if now.tzinfo is None:
        raise ValueError("now must include a timezone")
    local = now.astimezone(TIMEZONE)
    candidate = datetime.combine(local.date(), RUN_TIME, tzinfo=TIMEZONE)
    if candidate <= local:
        candidate = datetime.combine(local.date() + timedelta(days=1), RUN_TIME, tzinfo=TIMEZONE)
    return candidate
