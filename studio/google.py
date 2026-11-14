"""Sign in with Google (OAuth 2.0 authorization-code flow, no extra dependency).

Flow: the dashboard sends the browser to ``GET /api/auth/google``; we bounce it to
Google with a signed ``state`` that is also set as an HttpOnly cookie (the cookie
ties the round trip to *this* browser, which is what stops login CSRF). Google
returns to ``/api/auth/google/callback`` with a one-time ``code``; we exchange it
server-to-server for an access token, read the profile from the userinfo
endpoint, and hand the dashboard a normal studio session token in the URL hash
(a hash never reaches server logs).

Only configured when ``GOOGLE_CLIENT_ID`` and ``GOOGLE_CLIENT_SECRET`` are set.
"""

import hashlib
import hmac
import os
import secrets
import time
import urllib.parse
from typing import Optional

import httpx

from . import security

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
STATE_COOKIE = "vs_oauth_state"
STATE_TTL_SECONDS = 600
CALLBACK_PATH = "/api/auth/google/callback"


class GoogleError(Exception):
    """A failure the dashboard can describe with ``code``."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def client_id() -> str:
    return os.environ.get("GOOGLE_CLIENT_ID", "").strip()


def client_secret() -> str:
    return os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()


def enabled() -> bool:
    return bool(client_id() and client_secret())


def redirect_uri(request) -> str:
    """The callback URL registered in Google Cloud. An explicit
    ``GOOGLE_REDIRECT_URI`` wins; otherwise it is built from the address the
    browser used (``PUBLIC_API_URL`` first, since a TLS-terminating proxy makes
    the app see plain http)."""
    explicit = os.environ.get("GOOGLE_REDIRECT_URI", "").strip()
    if explicit:
        return explicit
    base = os.environ.get("PUBLIC_API_URL", "").rstrip("/") or str(request.base_url).rstrip("/")
    return base + CALLBACK_PATH


def frontend_url() -> str:
    """Where the dashboard lives. Empty = same origin as the API (the normal
    deployment, and the Vite dev proxy)."""
    return os.environ.get("STUDIO_FRONTEND_URL", "").rstrip("/")


def _sign(payload: str) -> str:
    key = security.signing_secret().encode("utf-8")
    return hmac.new(key, f"google-state:{payload}".encode(), hashlib.sha256).hexdigest()[:32]


def make_state(now: Optional[float] = None) -> str:
    expires = int((now if now is not None else time.time()) + STATE_TTL_SECONDS)
    nonce = secrets.token_urlsafe(16)
    payload = f"{nonce}.{expires}"
    return f"{payload}.{_sign(payload)}"


def check_state(state: str, cookie: str, now: Optional[float] = None) -> bool:
    """True only if ``state`` is ours, unexpired, and the same one this browser holds."""
    if not state or not cookie or not hmac.compare_digest(state, cookie):
        return False
    try:
        nonce, expires, sig = state.split(".")
        if not hmac.compare_digest(sig, _sign(f"{nonce}.{expires}")):
            return False
        return float(expires) >= (now if now is not None else time.time())
    except ValueError:
        return False


def authorize_url(request, state: str) -> str:
    query = urllib.parse.urlencode({
        "client_id": client_id(),
        "redirect_uri": redirect_uri(request),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
        "access_type": "online",
    })
    return f"{AUTH_URL}?{query}"


def fetch_profile(code: str, redirect: str, transport=None) -> dict:
    """Exchange ``code`` and return the verified Google profile.

    ``transport`` lets tests replace the network. Raises GoogleError.
    """
    try:
        with httpx.Client(timeout=15, transport=transport) as http:
            token = http.post(TOKEN_URL, data={
                "code": code, "client_id": client_id(), "client_secret": client_secret(),
                "redirect_uri": redirect, "grant_type": "authorization_code"})
            if token.status_code != 200:
                raise GoogleError("google_failed")
            access = token.json().get("access_token")
            if not access:
                raise GoogleError("google_failed")
            info = http.get(USERINFO_URL, headers={"Authorization": f"Bearer {access}"})
            if info.status_code != 200:
                raise GoogleError("google_failed")
            profile = info.json()
    except httpx.HTTPError:
        raise GoogleError("google_failed")
    if not profile.get("sub") or not profile.get("email"):
        raise GoogleError("google_failed")
    # An unverified address could belong to someone else; linking it to an
    # existing account would hand that account over.
    if profile.get("email_verified") is not True:
        raise GoogleError("google_unverified")
    return profile
