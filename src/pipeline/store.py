"""Settings and run history, kept in two protected tabs of the master sheet.

_settings  one row per setting:  key | value (JSON) | updated_at | updated_by
_runs      one row per run:      see RUNS_HEADER

Both the scheduled job and the API use this, so neither depends on the other.
The tabs are created and protected on first use: only the service account can
edit them, everyone with access to the sheet can still view them.
"""

import json
import logging
import os
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from uuid import uuid4

import gspread
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from pipeline.errors import PipelineError
from pipeline.google_auth import SHEETS_SCOPES, credentials
from pipeline.settings import (
    SECTION_LABELS,
    Settings,
    SettingsInvalid,
    load_defaults,
    parse_settings,
)

log = logging.getLogger(__name__)

SETTINGS_TAB = "_settings"
RUNS_TAB = "_runs"
SETTINGS_HEADER = ["key", "value", "updated_at", "updated_by"]
RUNS_HEADER = [
    "id",
    "started_at",
    "finished_at",
    "status",
    "trigger",
    "start_date",
    "end_date",
    "rows_written",
    "message",
    "triggered_by",
]

ALERTS_TAB = "_alerts"
ALERTS_HEADER = ["sent_at", "source", "metric", "drop_pct", "recent_total", "earlier_total", "weeks", "recipients"]

DEFAULTS_AUTHOR = "defaults (TBD placeholders)"

# A run still marked "running" after this long has almost certainly crashed.
# Treating it as failed means one crash can't block every future run.
STALE_AFTER = timedelta(hours=2)
STALE_MESSAGE = "This run stopped without finishing. It may have crashed or run out of time."

RunStatus = Literal["running", "success", "failed"]


class Run(BaseModel):
    id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: RunStatus
    trigger: Literal["scheduled", "manual"]
    start_date: date
    end_date: date
    rows_written: int | None = None
    message: str = ""
    triggered_by: str


class SettingsRecord(BaseModel):
    settings: Settings
    version: str  # updated_at of the last save; used to spot conflicting edits
    updated_by: str


class SettingsConflict(PipelineError):
    """Someone saved settings after this edit was started."""


def _now() -> datetime:
    return datetime.now(UTC)


def _pad(row: list[str], width: int) -> list[str]:
    # Sheets drops trailing empty cells, so short rows are normal.
    return row + [""] * (width - len(row))


def _run_to_row(run: Run) -> list:
    data = run.model_dump(mode="json")
    return ["" if data[column] is None else data[column] for column in RUNS_HEADER]


def _row_to_run(row: list[str]) -> Run:
    data = dict(zip(RUNS_HEADER, _pad(row, len(RUNS_HEADER))))
    for column in ("finished_at", "rows_written"):
        if data[column] == "":
            data[column] = None
    return Run.model_validate(data)


def _mark_stale(run: Run, now: datetime) -> Run:
    if run.status == "running" and now - run.started_at > STALE_AFTER:
        return run.model_copy(update={"status": "failed", "message": STALE_MESSAGE})
    return run


class Store:
    def __init__(self, spreadsheet, editor_email: str):
        self._spreadsheet = spreadsheet
        self._editor_email = editor_email
        self._lock_checked: set[str] = set()
        # Tabs this Store found unlocked and locked again, and when. Shown on the status page.
        self.relocked: dict[str, datetime] = {}

    @classmethod
    def open(cls) -> "Store":
        """Connect to the master sheet named by SPREADSHEET_ID."""
        load_dotenv()
        spreadsheet_id = os.environ.get("SPREADSHEET_ID", "").strip()
        if not spreadsheet_id:
            raise PipelineError("SPREADSHEET_ID is missing from .env, so the pipeline doesn't know which sheet to use.")
        creds = credentials(SHEETS_SCOPES)
        spreadsheet = gspread.authorize(creds).open_by_key(spreadsheet_id)
        return cls(spreadsheet, creds.service_account_email)

    # --- tabs ---------------------------------------------------------------

    def _tab(self, title: str, header: list[str]):
        try:
            worksheet = self._spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            worksheet = self._spreadsheet.add_worksheet(title=title, rows=100, cols=len(header))
            worksheet.append_row(header)
            self._protect(worksheet)
            self._lock_checked.add(title)
            return worksheet

        # The tab may have been made by hand, or its lock removed since. Settings
        # decide who gets alerts, so make sure it's locked before trusting it.
        if title not in self._lock_checked:
            if not self._is_locked(worksheet):
                log.warning("Tab %s wasn't locked; locking it again.", title)
                self._protect(worksheet)
                self.relocked[title] = _now()
            self._lock_checked.add(title)
        return worksheet

    def find_tab(self, title: str):
        """The tab if it exists (checked and locked like any other), else None. Never creates it."""
        try:
            self._spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            return None
        return self._tab(title, [])

    def tab(self, title: str, header: list[str]):
        """A locked tab for pipeline data (created with `header` if it doesn't exist yet)."""
        return self._tab(title, header)

    def _is_locked(self, worksheet) -> bool:
        """True if one protection covers the whole tab, blocks edits, and lets the pipeline edit.

        Extra named people are tolerated: Google always adds the sheet's owner, and only
        someone already allowed by the lock can add more. Groups and "anyone in the
        domain" are not, because they open the tab to people nobody picked.
        """
        metadata = self._spreadsheet.fetch_sheet_metadata(
            {"fields": "sheets(properties.sheetId,protectedRanges)"}
        )
        for sheet in metadata.get("sheets", []):
            if sheet["properties"].get("sheetId", 0) != worksheet.id:
                continue
            for protected in sheet.get("protectedRanges", []):
                whole_tab = set(protected["range"]) <= {"sheetId"}
                editors = protected.get("editors", {})
                if (
                    whole_tab
                    and not protected.get("warningOnly", False)
                    and not protected.get("unprotectedRanges")
                    and not editors.get("groups")
                    and not editors.get("domainUsersCanEdit", False)
                    and self._editor_email in editors.get("users", [])
                ):
                    return True
        return False

    def _protect(self, worksheet) -> None:
        protected_range = {
            "range": {"sheetId": worksheet.id},
            "description": "Managed by the pipeline. Change settings in the control panel instead.",
            "warningOnly": False,
            "editors": {"users": [self._editor_email]},
        }
        self._spreadsheet.batch_update(
            {"requests": [{"addProtectedRange": {"protectedRange": protected_range}}]}
        )

    # --- settings -----------------------------------------------------------

    def _settings_rows(self):
        worksheet = self._tab(SETTINGS_TAB, SETTINGS_HEADER)
        rows = [_pad(row, len(SETTINGS_HEADER)) for row in worksheet.get_all_values()[1:] if any(row)]
        return worksheet, rows

    @staticmethod
    def _newest(rows: list[list[str]]) -> list[str] | None:
        return max(rows, key=lambda row: row[2]) if rows else None

    def settings_meta(self) -> tuple[str | None, str | None]:
        """(version, updated_by) of the last save, even if the saved settings are invalid."""
        _, rows = self._settings_rows()
        newest = self._newest(rows)
        return (newest[2], newest[3]) if newest else (None, None)

    def read_settings(self) -> SettingsRecord:
        """Current settings. Seeds the TBD defaults the first time; raises SettingsInvalid if hand-edited badly."""
        _, rows = self._settings_rows()
        if not rows:
            return self.write_settings(load_defaults(), DEFAULTS_AUTHOR)

        data = {}
        for key, value, _, _ in rows:
            try:
                data[key] = json.loads(value)
            except json.JSONDecodeError:
                raise SettingsInvalid(
                    f"{SECTION_LABELS.get(key, key)}: the value in the {SETTINGS_TAB} tab "
                    "isn't in a format the pipeline can read."
                ) from None

        newest = self._newest(rows)
        return SettingsRecord(settings=parse_settings(data), version=newest[2], updated_by=newest[3])

    def write_settings(self, settings: Settings, user: str, expected_version: str | None = None) -> SettingsRecord:
        """Replace all settings. Pass expected_version to refuse overwriting someone else's newer save."""
        worksheet, rows = self._settings_rows()
        newest = self._newest(rows)
        if expected_version is not None and (newest[2] if newest else None) != expected_version:
            raise SettingsConflict("Someone else changed the settings. Reload and try again.")

        saved_at = _now().isoformat()
        values = [SETTINGS_HEADER] + [
            [key, json.dumps(value), saved_at, user]
            for key, value in settings.model_dump(mode="json").items()
        ]
        worksheet.clear()
        worksheet.update(values, "A1")
        return SettingsRecord(settings=settings, version=saved_at, updated_by=user)

    # --- runs ---------------------------------------------------------------

    def start_run(self, start: date, end: date, trigger: str, triggered_by: str) -> Run:
        run = Run(
            id=uuid4().hex[:12],
            started_at=_now(),
            status="running",
            trigger=trigger,
            start_date=start,
            end_date=end,
            triggered_by=triggered_by,
        )
        self._tab(RUNS_TAB, RUNS_HEADER).append_row(_run_to_row(run))
        return run

    def finish_run(self, run_id: str, status: RunStatus, rows_written: int | None, message: str) -> Run:
        worksheet = self._tab(RUNS_TAB, RUNS_HEADER)
        for line, row in enumerate(worksheet.get_all_values()[1:], start=2):
            if row and row[0] == run_id:
                run = _row_to_run(row).model_copy(
                    update={
                        "status": status,
                        "finished_at": _now(),
                        "rows_written": rows_written,
                        "message": message,
                    }
                )
                worksheet.update([_run_to_row(run)], f"A{line}")
                return run
        raise PipelineError(f"Couldn't find run {run_id} in the run history.")

    # --- alerts -------------------------------------------------------------

    def record_alert(self, row: list) -> None:
        """Log an alert email that was sent (one row per metric), so repeats can be held back."""
        self._tab(ALERTS_TAB, ALERTS_HEADER).append_row(row)

    def last_alerts(self) -> dict[tuple[str, str], datetime]:
        """When each (source, metric) was last emailed about."""
        worksheet = self.find_tab(ALERTS_TAB)
        latest: dict[tuple[str, str], datetime] = {}
        for row in (worksheet.get_all_values()[1:] if worksheet else []):
            row = _pad(row, len(ALERTS_HEADER))
            try:
                sent = datetime.fromisoformat(row[0])
            except ValueError:
                continue
            key = (row[1], row[2])
            latest[key] = max(sent, latest.get(key, sent))
        return latest

    def list_runs(self, limit: int = 20, now: datetime | None = None) -> list[Run]:
        """Runs newest first. Rows someone mangled by hand are skipped, not fatal."""
        now = now or _now()
        runs = []
        for row in self._tab(RUNS_TAB, RUNS_HEADER).get_all_values()[1:]:
            if not row or not row[0]:
                continue
            try:
                runs.append(_mark_stale(_row_to_run(row), now))
            except ValidationError:
                log.warning("Skipping unreadable row in %s: %r", RUNS_TAB, row)
        runs.sort(key=lambda run: run.started_at, reverse=True)
        return runs[:limit]

    def current_run(self, now: datetime | None = None) -> Run | None:
        """The run in progress, if any. Stale runs don't count."""
        return next((run for run in self.list_runs(limit=1000, now=now) if run.status == "running"), None)
