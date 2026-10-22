"""Settings validation and the TBD placeholder defaults. No network calls."""

import pytest

from pipeline.settings import (
    OLD_PLACEHOLDERS,
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


def test_defaults_are_marisols_choices():
    defaults = load_defaults()
    assert (defaults.metrics.ga4, defaults.metrics.search_console) == (["sessions", "totalUsers"], ["clicks", "impressions"])
    assert {m: t.drop_pct for m, t in defaults.alert_thresholds.items()} == {
        "sessions": 25, "totalUsers": 25, "clicks": 25, "impressions": 25,
    }
    assert defaults.alert_recipients == []  # alerts go to Slack
    assert placeholder_warnings(defaults) == []


TBD_FILE = '''
alert_recipients = []
[tbd]
sections = ["alert_thresholds"]
[metrics]
ga4 = ["sessions"]
search_console = ["clicks"]
[alert_thresholds]
sessions = { drop_pct = 50 }
'''


def test_a_section_marked_tbd_is_flagged_until_changed(tmp_path):
    defaults_file = tmp_path / "defaults.toml"
    defaults_file.write_text(TBD_FILE, encoding="utf-8")
    stand_in = load_defaults(defaults_file)

    assert placeholder_warnings(stand_in, defaults_file) == [
        "Alert thresholds still use the placeholder defaults and need to be set."
    ]
    changed = stand_in.model_copy(update={"alert_thresholds": {}})
    assert placeholder_warnings(changed, defaults_file) == []


def test_settings_saved_with_the_old_placeholders_are_still_flagged():
    # Saved before Marisol's choices: the reserved example.com address gives them away.
    old = parse_settings(valid(alert_recipients=["alerts-tbd@example.com"]))
    assert placeholder_warnings(old) == [OLD_PLACEHOLDERS]


def test_valid_settings_pass_and_emails_are_normalised():
    settings = parse_settings(valid(alert_recipients=["  Owner@JoinSWC.org "]))
    assert settings.alert_recipients == ["owner@joinswc.org"]


def test_bad_email_is_explained():
    assert problem(alert_recipients=["bob@"]) == "Alert recipients: 'bob@' isn't a valid email address."


def test_duplicate_recipients_rejected_case_insensitively():
    assert "listed twice" in problem(alert_recipients=["a@joinswc.org", "A@joinswc.org"])


def test_recipient_count_limits():
    assert parse_settings(valid(alert_recipients=[])).alert_recipients == []  # fine: alerts go to Slack
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
