"""Sign-in checks (CLAUDE.md rule 7). Google's token check is faked; no network."""

import subprocess
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from api import auth, dispatch
from api.main import app
from api.routes import get_dispatcher, get_store
from pipeline.store import Run

CLIENT_ID = "test-client.apps.googleusercontent.com"
ROUTES = [("get", "/status"), ("get", "/runs"), ("post", "/runs"), ("get", "/settings"), ("put", "/settings")]


def claims(email="owner@joinswc.org", hd="joinswc.org", verified=True):
    data = {"email": email, "email_verified": verified}
    if hd:
        data["hd"] = hd
    return data


@pytest.fixture
def client(store, monkeypatch):
    monkeypatch.setenv(auth.CLIENT_ID_ENV, CLIENT_ID)
    monkeypatch.delenv(auth.DOMAINS_ENV, raising=False)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_dispatcher] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def sign_in(monkeypatch, token_claims):
    def fake_verify(token, client_id):
        assert client_id == CLIENT_ID
        if token != "good-token":
            raise ValueError("bad signature")
        return token_claims

    monkeypatch.setattr(auth, "verify_token", fake_verify)


def get_runs(client, token="good-token"):
    return client.get("/runs", headers={"Authorization": f"Bearer {token}"})


@pytest.mark.parametrize("method, path", ROUTES)
def test_every_endpoint_needs_sign_in(client, method, path):
    response = getattr(client, method)(path)

    assert response.status_code == 401
    assert response.json() == {"detail": "Please sign in."}
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_locked_when_sign_in_not_set_up(client, monkeypatch):
    monkeypatch.delenv(auth.CLIENT_ID_ENV)
    sign_in(monkeypatch, claims())

    response = get_runs(client)
    assert response.status_code == 503
    assert "Sign-in isn't set up yet" in response.json()["detail"]


def test_invalid_or_expired_token(client, monkeypatch):
    sign_in(monkeypatch, claims())

    response = get_runs(client, token="forged")
    assert response.status_code == 401
    assert "expired or isn't valid" in response.json()["detail"]


@pytest.mark.parametrize(
    "email, hd",
    [("owner@joinswc.org", "joinswc.org"), ("Marisol@StarrWellnessCollective.org", "starrwellnesscollective.org")],
)
def test_both_business_domains_get_in(client, monkeypatch, email, hd):
    sign_in(monkeypatch, claims(email=email, hd=hd))
    assert get_runs(client).status_code == 200


@pytest.mark.parametrize(
    "token_claims",
    [
        claims(email="someone@gmail.com", hd=None),  # personal Google account
        claims(email="someone@otherbusiness.com", hd="otherbusiness.com"),  # another company's Workspace
        claims(verified=False),  # email address not verified
        claims(email="someone@gmail.com", hd="joinswc.org"),  # email doesn't match its domain
    ],
)
def test_other_accounts_are_turned_away(client, monkeypatch, token_claims):
    sign_in(monkeypatch, token_claims)

    response = get_runs(client)
    assert response.status_code == 403
    assert response.json()["detail"].startswith("This account isn't allowed to use the control panel.")


def test_allowed_domains_can_be_configured(client, monkeypatch):
    monkeypatch.setenv(auth.DOMAINS_ENV, "starrwellnesscollective.org")
    sign_in(monkeypatch, claims())  # joinswc.org

    assert get_runs(client).status_code == 403


def test_signed_in_email_is_recorded_on_run_now(client, monkeypatch, store):
    sign_in(monkeypatch, claims(email="Owner@JoinSWC.org"))
    app.dependency_overrides[get_dispatcher] = lambda: type("D", (), {"dispatch": lambda self, run: None})()

    response = client.post("/runs", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 202
    assert store.list_runs()[0].triggered_by == "owner@joinswc.org"


# --- local dispatcher ----------------------------------------------------------

def test_local_dispatcher_starts_runner_without_a_shell(monkeypatch):
    started = []
    monkeypatch.setattr(subprocess, "Popen", lambda args, **kwargs: started.append((args, kwargs)))
    run = Run(
        id="abc123", started_at=datetime(2026, 10, 21, 7, 0).astimezone(), status="running", trigger="manual",
        start_date=date(2026, 9, 1), end_date=date(2026, 9, 30), triggered_by="owner@joinswc.org",
    )

    dispatch.LocalDispatcher().dispatch(run)

    [(args, kwargs)] = started
    assert args[1:] == [
        "-m", "pipeline.runner", "--run-id", "abc123", "--start", "2026-09-01", "--end", "2026-09-30",
        "--trigger", "manual", "--triggered-by", "owner@joinswc.org",
    ]
    assert not kwargs.get("shell")
