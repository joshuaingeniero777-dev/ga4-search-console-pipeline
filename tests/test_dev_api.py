"""The local dev server works end to end on the pretend sheet, with no Google access."""

import time

from fastapi.testclient import TestClient

from api.main import app
from scripts import dev_api


def test_dev_api_runs_on_the_pretend_sheet():
    dev_api.configure(seconds=0)
    try:
        client = TestClient(app, headers={"Origin": "http://localhost:3000"})
        assert client.get("/status").json()["state"] == "ok"

        run_id = client.post("/runs").json()["run"]["id"]
        for _ in range(50):
            if client.get("/status").json()["state"] != "running":
                break
            time.sleep(0.05)

        [newest, _] = client.get("/runs").json()["runs"]
        assert (newest["id"], newest["status"], newest["triggered_by"]) == (run_id, "success", dev_api.DEV_USER)
    finally:
        app.dependency_overrides.clear()


def test_dev_api_only_listens_on_this_computer():
    assert dev_api.HOST == "127.0.0.1"
