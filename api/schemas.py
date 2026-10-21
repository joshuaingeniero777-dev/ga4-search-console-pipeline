"""Request and response shapes for the API. Run and Settings come from the pipeline, so both sides agree."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from pipeline.settings import Settings
from pipeline.store import Run


class StatusResponse(BaseModel):
    state: Literal["ok", "failed", "running", "never_run", "settings_invalid"]
    message: str  # one plain-English sentence or two, ready to show as-is
    warnings: list[str]
    last_run: Run | None
    next_run_at: datetime


class RunsResponse(BaseModel):
    runs: list[Run]


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date | None = None
    end_date: date | None = None


class RunResponse(BaseModel):
    run: Run


class MetricOption(BaseModel):
    name: str  # Google's name, used in settings
    label: str  # what the panel shows


class SettingsOptions(BaseModel):
    """What the settings form may offer, so the panel never keeps its own copy of the rules."""

    ga4: list[MetricOption]
    search_console: list[MetricOption]
    max_recipients: int
    min_drop_pct: int
    max_drop_pct: int


class SettingsResponse(BaseModel):
    settings: Settings | None  # None when what's saved breaks the rules; `problem` says why
    problem: str | None = None
    version: str | None  # send back with PUT so an edit can't overwrite a newer save
    updated_by: str | None
    warnings: list[str] = []
    options: SettingsOptions


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    settings: Settings
    version: str
