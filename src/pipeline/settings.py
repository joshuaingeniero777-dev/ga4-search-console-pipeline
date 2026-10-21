"""What the control panel's settings may contain, and the rules they must follow.

The same model validates settings coming from the control panel (PUT /settings)
and settings read back from the sheet, so a hand-edit that breaks the rules is
caught before the pipeline uses it.
"""

import re
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from pipeline.errors import PipelineError

DEFAULTS_PATH = Path(__file__).resolve().parents[2] / "config" / "settings.example.toml"

# Every metric the pipeline knows how to pull, by its Google API name.
# Which of these are actually used is a setting; this list is what's possible.
GA4_METRICS = Literal[
    "sessions",
    "totalUsers",
    "newUsers",
    "activeUsers",
    "screenPageViews",
    "engagedSessions",
    "engagementRate",
    "averageSessionDuration",
    "bounceRate",
    "keyEvents",
]
SEARCH_CONSOLE_METRICS = Literal["clicks", "impressions", "ctr", "position"]

MAX_RECIPIENTS = 10
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# How each part of the settings is named in messages the owner sees.
SECTION_LABELS = {
    "metrics": "Metrics",
    "ga4": "GA4",
    "search_console": "Search Console",
    "alert_thresholds": "Alert thresholds",
    "drop_pct": "drop %",
    "alert_recipients": "Alert recipients",
}


class SettingsInvalid(PipelineError):
    """Settings break the rules. The message says which one and why, in plain English."""


def _no_duplicates(values: list) -> list:
    if len(set(values)) != len(values):
        raise ValueError("the same entry is listed twice.")
    return values


class Metrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ga4: list[GA4_METRICS] = Field(min_length=1)
    search_console: list[SEARCH_CONSOLE_METRICS] = Field(min_length=1)

    _unique = field_validator("ga4", "search_console")(_no_duplicates)


class Threshold(BaseModel):
    model_config = ConfigDict(extra="forbid")

    drop_pct: int = Field(ge=1, le=100)


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metrics: Metrics
    alert_thresholds: dict[str, Threshold]
    alert_recipients: list[str] = Field(min_length=1, max_length=MAX_RECIPIENTS)

    @field_validator("alert_recipients")
    @classmethod
    def _valid_emails(cls, recipients: list[str]) -> list[str]:
        cleaned = [address.strip().lower() for address in recipients]
        for address in cleaned:
            if not EMAIL_PATTERN.match(address):
                raise ValueError(f"'{address}' isn't a valid email address.")
        return _no_duplicates(cleaned)

    @model_validator(mode="after")
    def _thresholds_match_metrics(self) -> "Settings":
        selected = set(self.metrics.ga4) | set(self.metrics.search_console)
        unknown = sorted(set(self.alert_thresholds) - selected)
        if unknown:
            raise ValueError(
                f"Alert thresholds are set for {', '.join(unknown)}, "
                "which isn't one of the metrics being pulled."
            )
        return self


def describe_errors(errors: list[dict], labels: dict[str, str | None] | None = None) -> str:
    """Rewrite pydantic's errors as one plain-English line per problem.

    `labels` adds or overrides names; a name mapped to None is left out of the location.
    """
    names = {**SECTION_LABELS, **(labels or {})}
    lines = []
    for problem in errors:
        # List positions (0, 1, ...) mean nothing to the owner, so they're left out.
        where = " > ".join(
            names.get(part, part)
            for part in problem["loc"]
            if isinstance(part, str) and names.get(part, part) is not None
        )
        message = problem["msg"].removeprefix("Value error, ")
        if problem["type"] == "literal_error":
            message = f"'{problem['input']}' isn't a metric the pipeline can pull."
        elif problem["type"] == "extra_forbidden":
            message = "this isn't a recognised setting."
        lines.append(f"{where}: {message}" if where else message)
    return " ".join(lines)


def parse_settings(data: dict) -> Settings:
    try:
        return Settings.model_validate(data)
    except ValidationError as error:
        raise SettingsInvalid(describe_errors(error.errors())) from None


def _read_defaults_file(path: Path) -> dict:
    with open(path, "rb") as file:
        return tomllib.load(file)


def load_defaults(path: Path = DEFAULTS_PATH) -> Settings:
    data = _read_defaults_file(path)
    data.pop("tbd", None)
    return parse_settings(data)


def placeholder_warnings(settings: Settings, path: Path = DEFAULTS_PATH) -> list[str]:
    """Plain-English warnings for each TBD section that still has its placeholder value."""
    data = _read_defaults_file(path)
    tbd = data.pop("tbd", {}).get("sections", [])
    defaults = parse_settings(data)
    return [
        f"{SECTION_LABELS[section]} still use the placeholder defaults and need to be set."
        for section in tbd
        if getattr(settings, section) == getattr(defaults, section)
    ]
