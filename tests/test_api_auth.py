"""Signing in with Google (CLAUDE.md rule 7). Google itself is faked; no network."""

import subprocess
from datetime import date, datetime, timedelta

import pytest
from authlib.integrations.starlette_client import OAuthError
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient

from api import auth, dispatch
from api.main import app
from api.routes import get_dispatcher, get_store
from pipeline.store import Run

PANEL = "http://localhost:3000"
ROUTES = [("get", "/status"), ("get", "/runs"), ("post", "/runs"), ("get", "/settings"), ("put", "/settings")]


class FakeGoogle:
    """Stands in for Google's sign-in: records where it was sent, returns chosen account details."""

    def __init__(self):
        self.claims = claims()
        self.error: str | None = None
        self.redirect_uri = None
        self.extra = None

    async def authorize_redirect(self, request, redirect_uri, **extra):
        self.redirect_uri, self.extra = redirect_uri, extra
        return RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?fake=1", 302)

    async def authorize_access_token(self, request):
        if self.error:
            raise OAuthError(error=self.error)
        return {"userinfo": self.claims}


def claims(email="owner@joinswc.org", hd="joinswc.org", verified=True, name="Owner"):
    data = {"email": email, "email_verified": verified, "name": name}
    if hd:
        data["hd"] = hd
    return data


@pytest.fixture
def google(monkeypatch):
    fake = FakeGoogle()
    monkeypatch.setattr(auth, "google_client", lambda: fake)
    return fake


@pytest.fixture
def client(store, google, monkeypatch):
    monkeypatch.setenv(auth.CLIENT_ID_ENV, "test-client.apps.googleusercontent.com")
    monkeypatch.setenv(auth.CLIENT_SECRET_ENV, "test-secret")
    monkeypatch.setenv(auth.SESSION_SECRET_ENV, "x" * 40)
    monkeypatch.delenv(auth.DOMAINS_ENV, raising=False)
    monkeypatch.delenv(auth.PANEL_ORIGIN_ENV, raising=False)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_dispatcher] = lambda: type("D", (), {"dispatch": lambda self, run: None})()
    yield TestClient(app, headers={"Origin": PANEL}, follow_redirects=False)
    app.dependency_overrides.clear()


def sign_in(client, next_page="/"):
    client.get("/auth/login", params={"next": next_page})
    return client.get("/auth/callback")


# --- the sign-in round trip ---------------------------------------------------

def test_login_sends_people_to_google_and_back_via_the_panel(client, google):
    response = client.get("/auth/login", params={"next": "/settings"})

    assert response.status_code == 302
    assert response.headers["location"].startswith("https://accounts.google.com/")
    assert google.redirect_uri == f"{PANEL}/backend/auth/callback"
    assert google.extra == {"prompt": "select_account", "hd": "*"}


def test_allowed_account_gets_a_session_and_lands_where_it_was_going(client):
    response = sign_in(client, "/settings")

    assert response.status_code == 303
    assert response.headers["location"] == "/settings"
    cookie = response.headers["set-cookie"]
    assert "panel_session=" in cookie and "httponly" in cookie.lower() and "samesite=lax" in cookie.lower()
    assert client.get("/auth/me").json() == {"email": "owner@joinswc.org", "name": "Owner"}
    assert client.get("/status").status_code == 200


@pytest.mark.parametrize(
    "email, hd",
    [("owner@joinswc.org", "joinswc.org"), ("Marisol@StarrWellnessCollective.org", "starrwellnesscollective.org")],
)
def test_both_business_domains_get_in(client, google, email, hd):
    google.claims = claims(email=email, hd=hd)
    sign_in(client)
    assert client.get("/auth/me").json()["email"] == email.lower()


@pytest.mark.parametrize(
    "token_claims",
    [
        claims(email="someone@gmail.com", hd=None),  # personal Google account
        claims(email="someone@otherbusiness.com", hd="otherbusiness.com"),  # another company's Workspace
        claims(verified=False),  # email address not verified
        claims(email="someone@gmail.com", hd="joinswc.org"),  # email doesn't match its domain
    ],
)
def test_other_accounts_are_turned_away(client, google, token_claims):
    google.claims = token_claims

    response = sign_in(client)

    assert response.headers["location"] == "/?signin=not_allowed"
    assert client.get("/auth/me").status_code == 401
    assert client.get("/status").status_code == 401


@pytest.mark.parametrize("error, outcome", [("access_denied", "cancelled"), ("mismatching_state", "failed")])
def test_sign_in_that_does_not_complete(client, google, error, outcome):
    google.error = error
    assert sign_in(client).headers["location"] == f"/?signin={outcome}"
    assert client.get("/auth/me").status_code == 401


@pytest.mark.parametrize("bad_next", ["https://evil.example", "//evil.example", "/\\evil.example", "settings"])
def test_never_sends_people_to_another_site_after_sign_in(client, bad_next):
    assert sign_in(client, bad_next).headers["location"] == "/"


def test_allowed_domains_can_be_configured(client, monkeypatch):
    monkeypatch.setenv(auth.DOMAINS_ENV, "starrwellnesscollective.org")
    assert sign_in(client).headers["location"] == "/?signin=not_allowed"  # joinswc.org


# --- sessions -------------------------------------------------------------------

@pytest.mark.parametrize("method, path", ROUTES)
def test_every_endpoint_needs_sign_in(client, method, path):
    response = getattr(client, method)(path)
    assert response.status_code == 401
    assert response.json() == {"detail": "Please sign in."}


def test_session_expires_after_eight_hours(client, monkeypatch):
    sign_in(client)
    later = datetime.now(auth.UTC) + auth.SESSION_LENGTH + timedelta(minutes=1)
    monkeypatch.setattr(auth, "_now", lambda: later)

    assert client.get("/status").status_code == 401


def test_sign_out(client):
    sign_in(client)
    assert client.post("/auth/logout").json() == {"signed_out": True}
    assert client.get("/status").status_code == 401


def test_session_cookie_cannot_be_forged(client):
    client.cookies.set("panel_session", "eyJ1c2VyIjogeyJlbWFpbCI6ICJ4QGpvaW5zd2Mub3JnIn19.forged.signature")
    assert client.get("/status").status_code == 401


def test_signed_in_email_is_recorded_on_run_now(client, google, store):
    google.claims = claims(email="Owner@JoinSWC.org")
    sign_in(client)

    assert client.post("/runs").status_code == 202
    assert store.list_runs()[0].triggered_by == "owner@joinswc.org"


# --- requests from other websites -------------------------------------------------

@pytest.mark.parametrize("origin", [None, "https://evil.example", "http://localhost:3001"])
@pytest.mark.parametrize("method, path", [("post", "/runs"), ("put", "/settings"), ("post", "/auth/logout")])
def test_changes_must_come_from_the_panel(client, origin, method, path):
    sign_in(client)
    headers = {"Origin": origin} if origin else {}
    client.headers.pop("Origin")

    response = getattr(client, method)(path, headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == auth.WRONG_ORIGIN


def test_reading_does_not_need_the_panel_origin(client):
    sign_in(client)
    client.headers.pop("Origin")
    assert client.get("/status").status_code == 200


# --- not set up -------------------------------------------------------------------

@pytest.mark.parametrize(
    "unset", [auth.CLIENT_ID_ENV, auth.CLIENT_SECRET_ENV, auth.SESSION_SECRET_ENV]
)
def test_locked_until_sign_in_is_set_up(client, monkeypatch, unset):
    monkeypatch.delenv(unset)

    for path in ("/status", "/auth/login", "/auth/me"):
        response = client.get(path)
        assert response.status_code == 503
        assert response.json()["detail"] == auth.NOT_SET_UP


def test_short_session_secret_counts_as_not_set_up(client, monkeypatch):
    monkeypatch.setenv(auth.SESSION_SECRET_ENV, "too-short")
    assert client.get("/status").status_code == 503


# --- local dispatcher ------------------------------------------------------------

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
