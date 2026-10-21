"""List every GA4 property the service account can see, with its numeric ID.

The pipeline needs the numeric GA4 property ID, which is easy to mistype or
confuse with the "G-XXXX" measurement ID. This asks Google directly instead.

Run from the repo root:  python scripts/list_ga4_properties.py
"""

from google.analytics.admin import AnalyticsAdminServiceClient
from google.api_core import exceptions

from pipeline.google_auth import credentials as load_credentials

SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]

EMPTY_MESSAGE = (
    "The service account can't see any GA4 properties. "
    "It probably hasn't been added in GA4 yet."
)


def collect_properties(summaries) -> list[dict]:
    """Flatten account summaries into one row per property."""
    rows = []
    for account in summaries:
        for prop in account.property_summaries:
            rows.append(
                {
                    "account": account.display_name,
                    "property": prop.display_name,
                    # Google returns "properties/123456789"; we only want the number.
                    "property_id": prop.property.split("/")[-1],
                }
            )
    return rows


def explain_error(error: Exception) -> str:
    """Turn a Google API error into a plain-English likely cause."""
    text = str(error)
    if isinstance(error, exceptions.PermissionDenied):
        if "SERVICE_DISABLED" in text or "has not been used" in text:
            return (
                "The Google Analytics Admin API is turned off in the Google Cloud "
                "project. Someone needs to enable it in the Cloud Console "
                "(APIs & Services > Library > Google Analytics Admin API)."
            )
        return "Google refused access. The service account probably hasn't been added in GA4."
    if isinstance(error, exceptions.Unauthenticated):
        return "Google rejected the key. service-account.json may be wrong, expired, or deleted."
    if isinstance(error, FileNotFoundError):
        return "service-account.json wasn't found. Run this from the project's main folder."
    return f"Something unexpected went wrong talking to Google ({type(error).__name__})."


def main() -> None:
    try:
        credentials = load_credentials(SCOPES)
        client = AnalyticsAdminServiceClient(credentials=credentials)
        rows = collect_properties(client.list_account_summaries())
    except Exception as error:
        print(f"Couldn't list GA4 properties. {explain_error(error)}")
        raise SystemExit(1)

    if not rows:
        print(EMPTY_MESSAGE)
        return

    print(f"{'Account':<30} {'Property':<35} Property ID")
    for row in rows:
        print(f"{row['account']:<30} {row['property']:<35} {row['property_id']}")


if __name__ == "__main__":
    main()
