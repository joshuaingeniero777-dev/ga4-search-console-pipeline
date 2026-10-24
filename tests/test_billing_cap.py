"""The billing cap's decision. The Cloud Billing API is faked; billing is never touched."""

import base64
import json

import pytest

from infra.billing_cap import cap

PROJECT = "ga4-search-console-pipeline"


def message(cost, budget=5.0, currency="USD"):
    return base64.b64encode(json.dumps(
        {"costAmount": cost, "budgetAmount": budget, "currencyCode": currency, "budgetDisplayName": "cap"}
    ).encode()).decode()


class FakeBilling:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.updates = []

    def projects(self):
        return self

    def getBillingInfo(self, name):
        self._result = {"name": name, "billingEnabled": self.enabled}
        return self

    def updateBillingInfo(self, name, body):
        self.updates.append((name, body))
        self.enabled = False
        self._result = {}
        return self

    def execute(self):
        return self._result


def test_under_the_cap_does_nothing():
    billing = FakeBilling()
    assert cap.handle(message(3.10), PROJECT, billing, dry_run=False) == (
        "Spent 3.10 USD of 5.00 USD this month. Under the cap; nothing to do."
    )
    assert billing.updates == []


@pytest.mark.parametrize("cost", [5.0, 5.01, 12.0])
def test_reaching_the_cap_switches_billing_off(cost):
    billing = FakeBilling()

    said = cap.handle(message(cost), PROJECT, billing, dry_run=False)

    assert billing.updates == [(f"projects/{PROJECT}", {"billingAccountName": ""})]
    assert "billing is now OFF" in said and "switch billing back on in Cloud Console" in said


def test_dry_run_only_says_what_it_would_do():
    billing = FakeBilling()
    said = cap.handle(message(6.0), PROJECT, billing, dry_run=True)
    assert said == f"Spent 6.00 USD of 5.00 USD. DRY RUN: would switch billing off for {PROJECT} now."
    assert billing.updates == []


def test_already_off_is_left_alone():
    billing = FakeBilling(enabled=False)
    assert "already off" in cap.handle(message(6.0), PROJECT, billing, dry_run=False)
    assert billing.updates == []


@pytest.mark.parametrize("bad", ["not base64 json!", base64.b64encode(b'{"costAmount": 6}').decode(), ""])
def test_unreadable_message_changes_nothing(bad):
    billing = FakeBilling()
    assert cap.handle(bad, PROJECT, billing, dry_run=False) == "Ignored a budget message that couldn't be read."
    assert billing.updates == []


def test_without_a_project_it_refuses_to_act():
    billing = FakeBilling()
    assert "CAP_PROJECT_ID isn't set" in cap.handle(message(6.0), "", billing, dry_run=False)
    assert billing.updates == []
