"""Next scheduled run: 6:00 AM America/New_York (decision 14)."""

from datetime import UTC, datetime

import pytest

from pipeline.schedule import TIMEZONE, next_run_at


def ny(*args) -> datetime:
    return datetime(*args, tzinfo=TIMEZONE)


def test_before_six_runs_same_day():
    assert next_run_at(ny(2026, 10, 21, 5, 59)) == ny(2026, 10, 21, 6, 0)


def test_at_or_after_six_runs_next_day():
    assert next_run_at(ny(2026, 10, 21, 6, 0)) == ny(2026, 10, 22, 6, 0)
    assert next_run_at(ny(2026, 10, 21, 23, 0)) == ny(2026, 10, 22, 6, 0)


def test_utc_input_uses_new_york_date():
    # 03:00 UTC on the 22nd is still 23:00 on the 21st in New York.
    result = next_run_at(datetime(2026, 10, 22, 3, 0, tzinfo=UTC))
    assert result == ny(2026, 10, 22, 6, 0)


def test_daylight_saving_change_keeps_six_am_local():
    # Clocks go back on 1 Nov 2026; the run stays at 6:00 local, now UTC-5.
    result = next_run_at(ny(2026, 10, 31, 23, 0))
    assert result.hour == 6
    assert result.utcoffset().total_seconds() == -5 * 3600


def test_requires_timezone():
    with pytest.raises(ValueError):
        # The missing timezone is the point of this test.
        next_run_at(datetime(2026, 10, 21, 5, 0))  # noqa: DTZ001
