"""Tests for the setup scripts' logic. No network calls; Google is never contacted."""

from datetime import date
from types import SimpleNamespace

from google.api_core import exceptions
from googleapiclient.errors import HttpError

from pipeline import errors
from scripts import access_check, list_ga4_properties


def http_error(status: int, body: bytes = b"{}") -> HttpError:
    return HttpError(SimpleNamespace(status=status, reason=""), body)


# --- list_ga4_properties ---------------------------------------------------

def test_collect_properties_flattens_and_strips_prefix():
    summaries = [
        SimpleNamespace(
            display_name="Account A",
            property_summaries=[
                SimpleNamespace(display_name="Site 1", property="properties/111"),
                SimpleNamespace(display_name="Site 2", property="properties/222"),
            ],
        ),
        SimpleNamespace(display_name="Empty account", property_summaries=[]),
    ]
    rows = list_ga4_properties.collect_properties(summaries)
    assert rows == [
        {"account": "Account A", "property": "Site 1", "property_id": "111"},
        {"account": "Account A", "property": "Site 2", "property_id": "222"},
    ]


def test_collect_properties_empty():
    assert list_ga4_properties.collect_properties([]) == []


def test_list_explains_disabled_api():
    error = exceptions.PermissionDenied("SERVICE_DISABLED: API has not been used")
    assert "turned off" in list_ga4_properties.explain_error(error)


def test_list_explains_permission_denied():
    error = exceptions.PermissionDenied("nope")
    assert "hasn't been added in GA4" in list_ga4_properties.explain_error(error)


# --- access_check ----------------------------------------------------------

def test_last_n_days_ends_yesterday():
    assert access_check.last_n_days(7, date(2026, 10, 16)) == ("2026-10-09", "2026-10-15")


def test_status_code_from_both_libraries():
    assert errors.status_code(http_error(403)) == 403
    assert errors.status_code(exceptions.NotFound("x")) == 404
    assert errors.status_code(ValueError("x")) is None


def test_403_means_not_added():
    message = errors.explain_error(http_error(403), "Search Console")
    assert "hasn't been added to the Search Console property" in message


def test_403_disabled_api_is_distinguished():
    message = errors.explain_error(http_error(403, b"SERVICE_DISABLED"), "GA4")
    assert "turned off" in message


def test_other_codes_have_plain_messages():
    assert "rejected the key" in errors.explain_error(http_error(401), "GA4")
    assert "couldn't find" in errors.explain_error(exceptions.NotFound("x"), "GA4")
    assert "wrong format" in errors.explain_error(exceptions.InvalidArgument("x"), "GA4")
    assert "wasn't found" in errors.explain_error(FileNotFoundError(), "GA4")


def test_missing_ga4_id_skips_without_crashing(monkeypatch, capsys):
    monkeypatch.setattr(access_check, "load_dotenv", lambda: None)
    monkeypatch.setenv("GSC_SITE_URL", "sc-domain:example.org")
    monkeypatch.delenv("GA4_PROPERTY_ID", raising=False)
    monkeypatch.setattr(access_check, "load_credentials", lambda *a, **k: object())
    monkeypatch.setattr(access_check, "search_console_clicks", lambda *a: [("2026-10-09", 3)])

    try:
        access_check.main()
    except SystemExit as exit_:
        assert exit_.code == 1  # a skipped check is reported as not passing

    out = capsys.readouterr().out
    assert "GA4: skipped. GA4_PROPERTY_ID is missing" in out
    assert "2026-10-09" in out
