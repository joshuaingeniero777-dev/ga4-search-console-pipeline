"""What Google Cloud runs when the $5 budget sends a message (see README.md).

Settings (set when it's deployed):
    CAP_PROJECT_ID   the project to switch billing off for
    CAP_DRY_RUN      "true" (the default) only logs what it would do; set "false" to arm it
"""

import logging
import os

import functions_framework
from cap import handle
from googleapiclient import discovery

logging.basicConfig(level=logging.INFO)


@functions_framework.cloud_event
def on_budget_message(cloud_event) -> None:
    dry_run = os.environ.get("CAP_DRY_RUN", "true").strip().lower() != "false"
    billing = discovery.build("cloudbilling", "v1", cache_discovery=False)
    handle(cloud_event.data["message"]["data"], os.environ.get("CAP_PROJECT_ID", "").strip(), billing, dry_run)
