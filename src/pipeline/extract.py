"""Pull one row per day from GA4 and Search Console. Read-only: nothing here writes anywhere.

Each function returns {"YYYY-MM-DD": {metric: number}}, only for the days the
source reported. A missing day means "no data yet" (Search Console runs 2-3
days behind), not zero, so the loader leaves that day alone.

To see what a run would pull, without writing anything:

    python -m pipeline.extract --start 2026-10-01 --end 2026-10-07
"""

import argparse
import os
from datetime import date

from dotenv import load_dotenv
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from googleapiclient.discovery import build

from pipeline import schedule
from pipeline.errors import PipelineError, explain_error
from pipeline.google_auth import READONLY_SCOPES, credentials
from pipeline.runner import default_range
from pipeline.settings import load_defaults

Daily = dict[str, dict[str, int | float]]

GA4_ROW_LIMIT = 100_000
SEARCH_CONSOLE_ROW_LIMIT = 25_000  # one row per day, so far more than 366 days ever needs
COUNT_METRICS = {"clicks", "impressions"}  # Search Console metrics that are whole numbers
DECIMALS = 4


def _setting(name: str, where_to_find: str) -> str:
    load_dotenv()
    value = os.environ.get(name, "").strip()
    if not value:
        raise PipelineError(f"{name} is missing from .env, so the pipeline doesn't know {where_to_find}.")
    return value


def ga4_property_id() -> str:
    return _setting("GA4_PROPERTY_ID", "which GA4 property to read")


def search_console_site() -> str:
    return _setting("GSC_SITE_URL", "which Search Console site to read")


def ga4_daily(client, property_id: str, metrics: list[str], start: date, end: date) -> Daily:
    response = client.run_report(
        RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name="date")],
            metrics=[Metric(name=name) for name in metrics],
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            limit=GA4_ROW_LIMIT,
        )
    )
    names = [header.name for header in response.metric_headers]
    whole = [header.type_.name == "TYPE_INTEGER" for header in response.metric_headers]
    daily: Daily = {}
    for row in response.rows:
        raw = row.dimension_values[0].value  # GA4 sends dates as YYYYMMDD
        day = f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
        daily[day] = {
            name: int(float(value.value)) if is_whole else round(float(value.value), DECIMALS)
            for name, value, is_whole in zip(names, row.metric_values, whole, strict=True)
        }
    return daily


def search_console_daily(service, site_url: str, metrics: list[str], start: date, end: date) -> Daily:
    body = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "dimensions": ["date"],
        "rowLimit": SEARCH_CONSOLE_ROW_LIMIT,
    }
    response = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
    return {
        row["keys"][0]: {
            name: int(row[name]) if name in COUNT_METRICS else round(float(row[name]), DECIMALS)
            for name in metrics
        }
        for row in response.get("rows", [])
    }


def fetch_ga4(start: date, end: date, metrics: list[str]) -> Daily:
    client = BetaAnalyticsDataClient(credentials=credentials(READONLY_SCOPES))
    return ga4_daily(client, ga4_property_id(), metrics, start, end)


def fetch_search_console(start: date, end: date, metrics: list[str]) -> Daily:
    service = build("searchconsole", "v1", credentials=credentials(READONLY_SCOPES), cache_discovery=False)
    return search_console_daily(service, search_console_site(), metrics, start, end)


def _print(title: str, daily: Daily, metrics: list[str]) -> None:
    print(f"\n{title}: {len(daily)} days")
    print("  " + "  ".join([f"{'date':<10}", *(f"{m:>14}" for m in metrics)]))
    for day in sorted(daily):
        print("  " + "  ".join([f"{day:<10}", *(f"{daily[day][m]:>14}" for m in metrics)]))


def main(argv: list[str] | None = None) -> None:
    first, last = default_range(schedule.today())  # the same days a scheduled run covers
    parser = argparse.ArgumentParser(description="Show what a run would pull. Writes nothing.")
    parser.add_argument("--start", type=date.fromisoformat, default=first)
    parser.add_argument("--end", type=date.fromisoformat, default=last)
    args = parser.parse_args(argv)
    metrics = load_defaults().metrics  # the placeholder set; real runs use the saved settings

    for title, fetch, chosen in (
        ("GA4", fetch_ga4, metrics.ga4),
        ("Search Console", fetch_search_console, metrics.search_console),
    ):
        try:
            _print(title, fetch(args.start, args.end, list(chosen)), list(chosen))
        except Exception as error:  # noqa: BLE001
            print(f"\n{title}: couldn't pull. {explain_error(error, title)}")


if __name__ == "__main__":
    main()
