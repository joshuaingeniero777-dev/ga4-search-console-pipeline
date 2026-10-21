"""Confirm the service account can actually read real data from both sources.

auth_check.py proves the key works. This goes one step further: it pulls a
week of numbers from Search Console and GA4, so a success here means access
has been granted on both properties.

Run from the repo root:  python scripts/access_check.py
"""

import os
from datetime import date, timedelta

from dotenv import load_dotenv
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from googleapiclient.discovery import build

from pipeline.errors import explain_error
from pipeline.google_auth import READONLY_SCOPES
from pipeline.google_auth import credentials as load_credentials

DAYS = 7


def last_n_days(n: int, today: date) -> tuple[str, str]:
    """Return (start, end) ISO dates for the n full days ending yesterday."""
    end = today - timedelta(days=1)
    start = end - timedelta(days=n - 1)
    return start.isoformat(), end.isoformat()


def print_table(title: str, header: str, rows: list[tuple[str, int]]) -> None:
    print(f"\n{title}")
    print(f"  {'Date':<12} {header}")
    if not rows:
        print("  (no data for these days)")
    for day, value in rows:
        print(f"  {day:<12} {value:,}")


def search_console_clicks(credentials, site_url: str, start: str, end: str) -> list[tuple[str, int]]:
    service = build("searchconsole", "v1", credentials=credentials, cache_discovery=False)
    response = (
        service.searchanalytics()
        .query(siteUrl=site_url, body={"startDate": start, "endDate": end, "dimensions": ["date"]})
        .execute()
    )
    return [(row["keys"][0], int(row["clicks"])) for row in response.get("rows", [])]


def ga4_sessions(credentials, property_id: str, start: str, end: str) -> list[tuple[str, int]]:
    client = BetaAnalyticsDataClient(credentials=credentials)
    response = client.run_report(
        RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name="date")],
            metrics=[Metric(name="sessions")],
            date_ranges=[DateRange(start_date=start, end_date=end)],
        )
    )
    rows = []
    for row in response.rows:
        raw = row.dimension_values[0].value  # GA4 returns dates as YYYYMMDD
        rows.append((f"{raw[:4]}-{raw[4:6]}-{raw[6:]}", int(row.metric_values[0].value)))
    return sorted(rows)


def main() -> None:
    load_dotenv()
    site_url = os.getenv("GSC_SITE_URL", "").strip()
    property_id = os.getenv("GA4_PROPERTY_ID", "").strip()
    start, end = last_n_days(DAYS, date.today())
    print(f"Checking {start} to {end}")

    try:
        credentials = load_credentials(READONLY_SCOPES)
    except Exception as error:
        print(f"Couldn't load the service account key. {explain_error(error, 'Google')}")
        raise SystemExit(1)

    ok = True

    if not site_url:
        print("\nSearch Console: skipped. GSC_SITE_URL is missing from .env.")
        ok = False
    else:
        try:
            print_table(f"Search Console clicks ({site_url})", "Clicks",
                        search_console_clicks(credentials, site_url, start, end))
            print("  Note: Search Console runs 2-3 days behind, so recent days may be missing.")
        except Exception as error:
            print(f"\nSearch Console: failed. {explain_error(error, 'Search Console')}")
            ok = False

    if not property_id:
        print("\nGA4: skipped. GA4_PROPERTY_ID is missing from .env. "
              "Run scripts/list_ga4_properties.py to find it.")
        ok = False
    else:
        try:
            print_table(f"GA4 sessions (property {property_id})", "Sessions",
                        ga4_sessions(credentials, property_id, start, end))
        except Exception as error:
            print(f"\nGA4: failed. {explain_error(error, 'GA4')}")
            ok = False

    print("\nAll access checks passed." if ok else "\nSome access checks did not pass. See above.")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
