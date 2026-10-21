"""Who is calling the API, and are they allowed to (CLAUDE.md rule 7).

The control panel signs people in with Google and sends the resulting ID token
as `Authorization: Bearer <token>`. Every endpoint checks that the token is
genuine, was issued for this app, and belongs to a verified account on one of
the business's Google Workspace domains (docs/decisions.md, decision 13).
"""

import os
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

CLIENT_ID_ENV = "GOOGLE_OAUTH_CLIENT_ID"
DOMAINS_ENV = "ALLOWED_DOMAINS"
DEFAULT_DOMAINS = "starrwellnesscollective.org,joinswc.org"

_bearer = HTTPBearer(auto_error=False)


def allowed_domains() -> set[str]:
    raw = os.environ.get(DOMAINS_ENV) or DEFAULT_DOMAINS
    return {domain.strip().lower() for domain in raw.split(",") if domain.strip()}


def verify_token(token: str, client_id: str) -> dict:
    """Check the token's signature, expiry, issuer and audience with Google. Raises ValueError if any fail."""
    return id_token.verify_oauth2_token(token, google_requests.Request(), client_id, clock_skew_in_seconds=10)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


def current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]) -> str:
    """The signed-in person's email address, or a 401/403/503 explaining why not."""
    client_id = os.environ.get(CLIENT_ID_ENV, "").strip()
    if not client_id:
        # Fail closed: without a client ID no token can be checked, so nobody gets in.
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Sign-in isn't set up yet ({CLIENT_ID_ENV} is missing), so the control panel is locked.",
        )
    if credentials is None:
        raise _unauthorized("Please sign in.")

    try:
        claims = verify_token(credentials.credentials, client_id)
    except ValueError:
        raise _unauthorized("Your sign-in has expired or isn't valid. Please sign in again.") from None

    email = str(claims.get("email", "")).lower()
    domain = str(claims.get("hd", "")).lower()
    if not claims.get("email_verified") or domain not in allowed_domains() or not email.endswith("@" + domain):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This account isn't allowed to use the control panel. "
            f"Sign in with a {' or '.join(sorted(allowed_domains()))} account.",
        )
    return email
