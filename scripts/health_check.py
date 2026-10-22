"""Is everything working? A plain-English checklist. READ-ONLY: it can't change anything.

Run from the repo root:  python -m scripts.health_check
(or ask Claude Code for /health-check)

Every Google connection here uses read-only permissions, so even a bug couldn't
write to the sheet. It never posts to Slack; it only checks the link is there.
"""

import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from typing import NamedTuple

import gspread
from dotenv import load_dotenv
from google.auth.transport.requests import Request

from api.auth import missing_settings
from pipeline import extract, schedule
from pipeline.errors import PipelineError, explain_error
from pipeline.google_auth import READONLY_SCOPES, credentials
from pipeline.load import GA4_TAB, SEARCH_CONSOLE_TAB
from pipeline.runner import default_range
from pipeline.settings import SettingsInvalid, placeholder_warnings
from pipeline.store import RUNS_TAB, SETTINGS_TAB, Store

SHEETS_READ_ONLY = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
LOCKED_TABS = [SETTINGS_TAB, RUNS_TAB, GA4_TAB, SEARCH_CONSOLE_TAB]


class Check(NamedTuple):
    name: str
    ok: bool
    detail: str


def _when(moment: datetime) -> str:
    local = moment.astimezone(schedule.TIMEZONE)
    return f"{local:%a} {local.day} {local:%b}, {local:%I:%M %p}".replace(" 0", " ")


def check_key() -> Check:
    try:
        key = credentials(READONLY_SCOPES)
        key.refresh(Request())
    except Exception as error:  # noqa: BLE001
        return Check("Google key", False, explain_error(error, "Google"))
    return Check("Google key", True, "The pipeline's Google key works.")


def check_sheet(store: Store, sheet_title: str) -> list[Check]:
    """`store` must be read-only: it reports unlocked or missing tabs instead of fixing them."""
    checks = [Check("Master sheet", True, f'Can read "{sheet_title}".')]

    try:
        warnings = placeholder_warnings(store.read_settings().settings)
        checks.append(Check("Settings", not warnings, " ".join(warnings) or "Settings are filled in and valid."))
    except (SettingsInvalid, PipelineError) as error:
        checks.append(Check("Settings", False, f"The saved settings have a problem: {error}"))

    try:
        runs = store.list_runs(limit=1000)
    except PipelineError as error:
        runs = []
        checks.append(Check("Run history", False, str(error)))
    finished = next((r for r in runs if r.status != "running"), None)
    if finished is None:
        checks.append(Check("Last run", False, "The pipeline hasn't run yet."))
    elif finished.status == "success":
        checks.append(Check("Last run", True, f"Worked ({_when(finished.started_at)}). {finished.message}"))
    else:
        checks.append(Check("Last run", False, f"Failed ({_when(finished.started_at)}). {finished.message}"))
    if any(r.status == "running" for r in runs):
        checks.append(Check("Running now", True, "A run is in progress."))

    for title in LOCKED_TABS:
        store.find_tab(title)  # notes the tab in store.unlocked if its lock is missing
    unlocked = sorted(store.unlocked)
    checks.append(
        Check("Locked tabs", not unlocked,
              f"Not locked: {', '.join(unlocked)}. The next run locks them again."
              if unlocked else "The pipeline's tabs are locked.")
    )
    return checks


def check_sources(fetchers: dict[str, Callable] | None = None) -> list[Check]:
    fetchers = fetchers or {"GA4": extract.fetch_ga4, "Search Console": extract.fetch_search_console}
    metrics = {"GA4": ["sessions"], "Search Console": ["clicks"]}
    start, end = default_range(schedule.today())
    checks = []
    for source, fetch in fetchers.items():
        try:
            days = len(fetch(start, end, metrics[source]))
        except Exception as error:  # noqa: BLE001
            checks.append(Check(source, False, f"Can't read it. {explain_error(error, source)}"))
            continue
        checks.append(Check(source, True, f"Can read it ({days} of the last 7 days reported so far)."))
    return checks


def check_setup() -> list[Check]:
    load_dotenv()
    # The same rule as pipeline/slack.py: only a real Slack link counts. Never posted to here.
    slack_ok = os.environ.get("SLACK_WEBHOOK_URL", "").strip().startswith("https://hooks.slack.com/")
    sign_in_missing = missing_settings()
    return [
        Check("Slack alerts", slack_ok, "The Slack link is set up." if slack_ok
              else "No Slack link (SLACK_WEBHOOK_URL) is set up, so alerts are off."),
        Check("Control panel sign-in", not sign_in_missing, "Sign-in is set up." if not sign_in_missing
              else "Sign-in isn't set up here, so the control panel is locked on this computer."),
        Check("Next scheduled run", True, f"{_when(schedule.next_run_at(datetime.now(UTC)))} (New York time), "
              "once the pipeline is running in the cloud. Until then, nothing runs by itself."),
    ]


def run_checks() -> list[Check]:
    checks = [check_key()]
    if not checks[0].ok:
        return checks  # nothing else can work without the key
    load_dotenv()
    try:
        readonly = credentials(SHEETS_READ_ONLY)
        sheet = gspread.authorize(readonly).open_by_key(os.environ.get("SPREADSHEET_ID", "").strip())
        checks += check_sheet(Store(sheet, readonly.service_account_email, read_only=True), sheet.title)
    except Exception as error:  # noqa: BLE001
        checks.append(Check("Master sheet", False, f"Can't read it. {explain_error(error, 'Google Sheets')}"))
    return checks + check_sources() + check_setup()


def report(checks: list[Check]) -> str:
    lines = [f"{'OK ' if c.ok else 'NO '} {c.name}: {c.detail}" for c in checks]
    problems = sum(not c.ok for c in checks)
    lines.append("")
    lines.append("Everything looks fine." if not problems else f"{problems} thing(s) need attention (marked NO).")
    return "\n".join(lines)


def main() -> None:
    checks = run_checks()
    print(report(checks))
    sys.exit(0 if all(c.ok for c in checks) else 1)


if __name__ == "__main__":
    main()
