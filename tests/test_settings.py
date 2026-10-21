"""Settings validation and the TBD placeholder defaults. No network calls."""

import pytest

from pipeline.settings import (
    SettingsInvalid,
    load_defaults,
    metric_options,
    parse_settings,
    placeholder_warnings,
)


def valid(**overrides) -> dict:
    data = {
        "metrics": {"ga4": ["sessions"], "search_console": ["clicks"]},
        "alert_thresholds": {"sessions": {"drop_pct": 25}},
        "alert_recipients": ["owner@joinswc.org"],
    }
    data.update(overrides)
    return data


def problem(**overrides) -> str:
    with pytest.raises(SettingsInvalid) as caught:
        parse_settings(valid(**overrides))
    return str(caught.value)


def test_defaults_file_is_valid():
    defaults = load_defaults()
    assert defaults.metrics.ga4 and defaults.metrics.search_console


def test_defaults_are_flagged_as_tbd():
    warnings = placeholder_warnings(load_defaults())
    assert len(warnings) == 3
    assert any("Alert recipients" in warning for warning in warnings)


def test_tbd_warning_clears_once_a_section_is_changed():
    settings = load_defaults().model_copy(update={"alert_recipients": ["owner@joinswc.org"]})
    warnings = placeholder_warnings(settings)
    assert not any("Alert recipients" in warning for warning in warnings)
    assert len(warnings) == 2


def test_placeholder_recipient_cannot_receive_mail():
    # example.com is reserved, so a forgotten placeholder can't email a stranger.
    assert all(address.endswith("@example.com") for address in load_defaults().alert_recipients)


def test_valid_settings_pass_and_emails_are_normalised():
    settings = parse_settings(valid(alert_recipients=["  Owner@JoinSWC.org "]))
    assert settings.alert_recipients == ["owner@joinswc.org"]


def test_bad_email_is_explained():
    assert problem(alert_recipients=["bob@"]) == "Alert recipients: 'bob@' isn't a valid email address."


def test_duplicate_recipients_rejected_case_insensitively():
    assert "listed twice" in problem(alert_recipients=["a@joinswc.org", "A@joinswc.org"])


def test_recipient_count_limits():
    assert "Alert recipients" in problem(alert_recipients=[])
    assert "Alert recipients" in problem(alert_recipients=[f"p{n}@joinswc.org" for n in range(11)])


def test_unknown_metric_is_explained():
    message = problem(metrics={"ga4": ["pageviews"], "search_console": ["clicks"]})
    assert message == "Metrics > GA4: 'pageviews' isn't a metric the pipeline can pull."


def test_each_source_needs_a_metric():
    assert "Metrics > Search Console" in problem(metrics={"ga4": ["sessions"], "search_console": []})


def test_duplicate_metric_rejected():
    assert "listed twice" in problem(metrics={"ga4": ["sessions", "sessions"], "search_console": ["clicks"]})


@pytest.mark.parametrize("drop_pct", [0, 101])
def test_threshold_out_of_range(drop_pct):
    message = problem(alert_thresholds={"sessions": {"drop_pct": drop_pct}})
    assert message.startswith("Alert thresholds > sessions > drop %:")


def test_threshold_must_be_for_a_pulled_metric():
    message = problem(alert_thresholds={"impressions": {"drop_pct": 10}})
    assert "impressions" in message and "isn't one of the metrics being pulled" in message


def test_unknown_setting_rejected():
    assert "isn't a recognised setting" in problem(colour="blue")


def test_every_allowed_metric_has_a_display_name():
    options = metric_options()
    assert [m["name"] for m in options["search_console"]] == ["clicks", "impressions", "ctr", "position"]
    assert all(m["label"] for source in options.values() for m in source)
