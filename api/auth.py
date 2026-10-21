"""Signing in to the control panel with Google (CLAUDE.md rule 7).

Sign-in happens here in the API, so only api/ ever talks to Google (rule 6).
The panel forwards /backend/* to this API, so the browser sees these routes on
the panel's own address and the session cookie belongs to the panel's site:

    /auth/login     sends the person to Google's sign-in page
    /auth/callback  where Google sends them back; checks who they are
    /auth/me        who is signed in (the panel asks on every page)
    /auth/logout    forgets the sign-in

Only a verified account on one of the business's Workspace domains gets a
session (docs/decisions.md, decision 13). Every other endpoint needs that
session, and anything that changes something must come from the panel's own
address, so another website can't make a signed-in browser do it.
"""

import logging
import os
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Annotated

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse

log = logging.getLogger(__name__)

CLIENT_ID_ENV = "GOOGLE_OAUTH_CLIENT_ID"
CLIENT_SECRET_ENV = "GOOGLE_OAUTH_CLIENT_SECRET"
SESSION_SECRET_ENV = "SESSION_SECRET"
DOMAINS_ENV = "ALLOWED_DOMAINS"
PANEL_ORIGIN_ENV = "PANEL_ORIGIN"

DEFAULT_DOMAINS = "starrwellnesscollective.org,joinswc.org"
DEFAULT_PANEL_ORIGIN = "http://localhost:3000"
GOOGLE_DISCOVERY = "https://accounts.google.com/.well-known/openid-configuration"

SESSION_KEY = "user"
SESSION_LENGTH = timedelta(hours=8)
MIN_SESSION_SECRET = 32  # characters; shorter is too easy to guess
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

NOT_SET_UP = "Sign-in isn't set up yet, so the control panel is locked."
WRONG_ORIGIN = "This request didn't come from the control panel, so it was refused."


def _now() -> datetime:
    return datetime.now(UTC)


def allowed_domains() -> set[str]:
    raw = os.environ.get(DOMAINS_ENV) or DEFAULT_DOMAINS
    return {domain.strip().lower() for domain in raw.split(",") if domain.strip()}


def panel_origin() -> str:
    return (os.environ.get(PANEL_ORIGIN_ENV) or DEFAULT_PANEL_ORIGIN).rstrip("/")


def missing_settings() -> list[str]:
    """Which sign-in settings are missing or unusable. Empty means sign-in can work."""
    missing = [name for name in (CLIENT_ID_ENV, CLIENT_SECRET_ENV) if not os.environ.get(name, "").strip()]
    if len(os.environ.get(SESSION_SECRET_ENV, "")) < MIN_SESSION_SECRET:
        missing.append(SESSION_SECRET_ENV)
    return missing


def _require_set_up() -> None:
    missing = missing_settings()
    if missing:
        # Fail closed: without these nobody can be checked, so nobody gets in.
        log.warning("Sign-in is locked; missing or too short: %s", ", ".join(missing))
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NOT_SET_UP)


@lru_cache
def _google(client_id: str, client_secret: str):
    oauth = OAuth()
    oauth.register(
        "google",
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url=GOOGLE_DISCOVERY,
        client_kwargs={"scope": "openid email profile", "code_challenge_method": "S256"},
    )
    return oauth.google


def google_client():
    return _google(os.environ[CLIENT_ID_ENV].strip(), os.environ[CLIENT_SECRET_ENV].strip())


def allowed_email(claims: dict) -> str | None:
    """The account's email if it may use the panel, else None."""
    email = str(claims.get("email", "")).lower()
    domain = str(claims.get("hd", "")).lower()
    if claims.get("email_verified") and domain in allowed_domains() and email.endswith("@" + domain):
        return email
    return None


def safe_next(path: str | None) -> str:
    """Only send people back to a page on the panel itself, never to another site."""
    if path and path.startswith("/") and not path.startswith("//") and "\\" not in path:
        return path
    return "/"


def current_user(request: Request) -> str:
    """The signed-in person's email address, or a 401/503 explaining why not."""
    _require_set_up()
    session = request.session.get(SESSION_KEY)
    if not session or session.get("expires", 0) < _now().timestamp():
        request.session.pop(SESSION_KEY, None)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in.")
    return session["email"]


def from_panel(request: Request) -> None:
    """Refuse changes (saves, runs, sign-out) unless the browser says they came from the panel."""
    if request.method in UNSAFE_METHODS and request.headers.get("origin", "").rstrip("/") != panel_origin():
        raise HTTPException(status.HTTP_403_FORBIDDEN, WRONG_ORIGIN)


router = APIRouter(prefix="/auth", dependencies=[Depends(from_panel)])


@router.get("/login")
async def login(request: Request, next: str = "/"):
    _require_set_up()
    request.session["next"] = safe_next(next)
    # Google sends people back to the panel's address, which forwards to /auth/callback here.
    redirect_uri = f"{panel_origin()}/backend/auth/callback"
    # hd="*" only lists Workspace accounts on Google's screen; the real check is in callback().
    return await google_client().authorize_redirect(request, redirect_uri, prompt="select_account", hd="*")


@router.get("/callback")
async def callback(request: Request):
    _require_set_up()
    target = safe_next(request.session.pop("next", "/"))
    try:
        token = await google_client().authorize_access_token(request)
    except OAuthError as error:
        log.warning("Sign-in didn't complete: %s", error.error)
        outcome = "cancelled" if error.error == "access_denied" else "failed"
        return RedirectResponse(f"/?signin={outcome}", status.HTTP_303_SEE_OTHER)

    claims = token.get("userinfo") or {}
    email = allowed_email(claims)
    request.session.clear()  # a fresh session on every sign-in
    if not email:
        log.info("Turned away a sign-in from %s", claims.get("hd") or "a non-Workspace account")
        return RedirectResponse("/?signin=not_allowed", status.HTTP_303_SEE_OTHER)

    request.session[SESSION_KEY] = {
        "email": email,
        "name": str(claims.get("name", "")),
        "expires": (_now() + SESSION_LENGTH).timestamp(),
    }
    return RedirectResponse(target, status.HTTP_303_SEE_OTHER)


@router.get("/me")
def me(request: Request, email: Annotated[str, Depends(current_user)]) -> dict:
    session = request.session.get(SESSION_KEY) or {}
    return {"email": email, "name": session.get("name", "")}


@router.post("/logout")
def logout(request: Request) -> dict:
    request.session.clear()
    return {"signed_out": True}
