"""The billing cap's decision: has spending reached the budget? Then switch billing off.

Google Cloud budgets can only warn; they never stop spending. This closes that gap
(docs/decisions.md, decision 9). The $5 budget sends a message to this function
several times a day with the month's cost so far. When the cost reaches the budget,
the project is unlinked from its billing account, which stops everything that costs
money. Nothing switches billing back on automatically; a person does that in
Cloud Console.

Kept apart from main.py (the part Google runs) so it can be tested without Google.
"""

import base64
import json
import logging

log = logging.getLogger("billing_cap")


def read_notification(encoded: str) -> dict | None:
    """The budget's message (base64 JSON from Pub/Sub), or None if it can't be read."""
    try:
        message = json.loads(base64.b64decode(encoded))
        return {
            "cost": float(message["costAmount"]),
            "budget": float(message["budgetAmount"]),
            "currency": message.get("currencyCode", ""),
        }
    except (ValueError, KeyError, TypeError):
        return None


def handle(encoded: str, project_id: str, billing, dry_run: bool) -> str:
    """Act on one budget message. Returns a plain-English line, which is also logged."""
    notification = read_notification(encoded)
    if notification is None:
        return _say("Ignored a budget message that couldn't be read.", logging.WARNING)
    if not project_id:
        return _say("CAP_PROJECT_ID isn't set, so the cap can't act. Nothing was changed.", logging.ERROR)

    cost, budget, currency = notification["cost"], notification["budget"], notification["currency"]
    spent = f"{cost:.2f} {currency} of {budget:.2f} {currency}".strip()
    if cost < budget:
        return _say(f"Spent {spent} this month. Under the cap; nothing to do.")

    name = f"projects/{project_id}"
    projects = billing.projects()
    if not projects.getBillingInfo(name=name).execute().get("billingEnabled"):
        return _say(f"Spent {spent}. Billing is already off for {project_id}; nothing to do.")
    if dry_run:
        return _say(f"Spent {spent}. DRY RUN: would switch billing off for {project_id} now.", logging.WARNING)

    projects.updateBillingInfo(name=name, body={"billingAccountName": ""}).execute()
    return _say(
        f"Spent {spent}: the cap was reached, so billing is now OFF for {project_id}. "
        "The pipeline has stopped. A person can switch billing back on in Cloud Console.",
        logging.WARNING,
    )


def _say(text: str, level: int = logging.INFO) -> str:
    log.log(level, text)
    return text
