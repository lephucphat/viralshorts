"""Sign in with Google: the state check, the profile fetch, and the two routes."""
import urllib.parse

import httpx
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from studio import api, auth, db, google


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_DB_PATH", str(tmp_path / "studio.db"))
    monkeypatch.setenv("STUDIO_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "shh")
    monkeypatch.delenv("GOOGLE_REDIRECT_URI", raising=False)
    monkeypatch.delenv("STUDIO_FRONTEND_URL", raising=False)
    db._initialised_for = None
    auth.clear_all_throttles()
    ctx = api.Context(job_status=lambda j: None, cancel_job=lambda j: False,
                      remove_job_files=lambda j: None)
    app = FastAPI()
    app.include_router(api.build_router(ctx))
    return TestClient(app, follow_redirects=False)


def _fake_google(monkeypatch, profile, token_status=200):
    """Route fetch_profile's HTTP calls to canned answers."""
    def handler(request):
        if request.url.path.endswith("/token"):
            return httpx.Response(token_status, json={"access_token": "at"})
        return httpx.Response(200, json=profile)

    real = google.fetch_profile
    monkeypatch.setattr(google, "fetch_profile",
                        lambda code, redirect, transport=None: real(
                            code, redirect, transport=httpx.MockTransport(handler)))


PROFILE = {"sub": "g-1", "email": "Ann@Example.com", "email_verified": True,
           "name": "Ann Nguyen", "picture": "https://x/p.png", "locale": "vi"}


# --------------------------------------------------------------------------- #
def test_state_roundtrip_and_tampering(monkeypatch):
    monkeypatch.setenv("STUDIO_SECRET", "s")
    state = google.make_state()
    assert google.check_state(state, state)
    assert not google.check_state(state, "")                      # no cookie
    assert not google.check_state(state, google.make_state())     # another browser's
    nonce, exp, sig = state.split(".")
    assert not google.check_state(f"{nonce}.{int(exp) + 999}.{sig}", f"{nonce}.{int(exp) + 999}.{sig}")
    assert not google.check_state("garbage", "garbage")


def test_state_expires():
    state = google.make_state(now=1000)
    assert google.check_state(state, state, now=1000 + google.STATE_TTL_SECONDS - 1)
    assert not google.check_state(state, state, now=1000 + google.STATE_TTL_SECONDS + 5)


def test_not_configured_means_404(env, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID")
    assert env.get("/api/auth/google").status_code == 404
    assert env.get("/api/auth/google/callback?code=x&state=y").status_code == 404


def test_start_redirects_to_google_with_a_bound_state(env):
    r = env.get("/api/auth/google", headers={"host": "app.example.com"})
    assert r.status_code == 302
    url = urllib.parse.urlparse(r.headers["location"])
    q = urllib.parse.parse_qs(url.query)
    assert url.netloc == "accounts.google.com"
    assert q["client_id"] == ["cid.apps.googleusercontent.com"]
    assert q["redirect_uri"] == ["http://app.example.com/api/auth/google/callback"]
    assert q["scope"] == ["openid email profile"]
    cookie = r.headers["set-cookie"]
    assert q["state"][0] in cookie and "HttpOnly" in cookie and "samesite=lax" in cookie.lower()


def test_explicit_redirect_uri_wins(env, monkeypatch):
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://vs.example/api/auth/google/callback")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(env.get("/api/auth/google").headers["location"]).query)
    assert q["redirect_uri"] == ["https://vs.example/api/auth/google/callback"]


def _start(env):
    r = env.get("/api/auth/google")
    return urllib.parse.parse_qs(urllib.parse.urlparse(r.headers["location"]).query)["state"][0]


def test_callback_creates_an_account_and_hands_over_a_session(env, monkeypatch):
    _fake_google(monkeypatch, PROFILE)
    state = _start(env)
    r = env.get(f"/api/auth/google/callback?code=abc&state={state}")
    assert r.status_code == 302
    loc = r.headers["location"]
    assert loc.startswith("/#/auth/callback?token=")
    token = urllib.parse.unquote(loc.split("token=")[1])
    me = env.get("/api/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]
    assert me["email"] == "ann@example.com" and me["name"] == "Ann Nguyen"
    assert me["has_google"] is True and me["has_password"] is False


def test_callback_without_the_matching_cookie_is_refused(env, monkeypatch):
    _fake_google(monkeypatch, PROFILE)
    state = _start(env)
    env.cookies.clear()                       # a different browser finishes the flow
    r = env.get(f"/api/auth/google/callback?code=abc&state={state}")
    assert r.headers["location"] == "/#/login?error=google_failed"


def test_cancelled_consent(env):
    assert env.get("/api/auth/google/callback?error=access_denied").headers["location"] == "/#/login?error=google_denied"


def test_unverified_email_is_never_linked(env, monkeypatch):
    victim = auth.register("ann@example.com", "correct horse")
    _fake_google(monkeypatch, {**PROFILE, "email_verified": False})
    state = _start(env)
    r = env.get(f"/api/auth/google/callback?code=abc&state={state}")
    assert r.headers["location"] == "/#/login?error=google_unverified"
    assert auth.get(victim.id).has_google is False


def _verify(user_id):
    with db.connection() as c:
        c.execute("UPDATE users SET email_verified_at = ? WHERE id = ?", (db.now(), user_id))


def test_google_links_to_the_verified_password_account_of_the_same_email(env, monkeypatch):
    existing = auth.register("ann@example.com", "correct horse", "Ann")
    _verify(existing.id)                                      # the owner proved the inbox before
    _fake_google(monkeypatch, PROFILE)
    state = _start(env)
    env.get(f"/api/auth/google/callback?code=abc&state={state}")
    linked = auth.get(existing.id)
    assert linked.has_google and linked.has_password          # same account, both ways in
    again = auth.login_with_google("g-1", "ann@example.com")
    assert again.id == existing.id


def test_google_link_to_an_unverified_account_drops_the_squatters_password(env, monkeypatch):
    """Pre-hijacking: an attacker registers the victim's address with a password they know.
    When the real owner later signs in with Google, that password and its sessions must die."""
    squatted = auth.register("ann@example.com", "attacker password")
    attacker_token = auth.issue_token(squatted)
    _fake_google(monkeypatch, PROFILE)
    state = _start(env)
    env.get(f"/api/auth/google/callback?code=abc&state={state}")
    linked = auth.get(squatted.id)
    assert linked.has_google and not linked.has_password and linked.email_verified
    assert auth.user_from_token(attacker_token) is None       # the old session is revoked
    with pytest.raises(auth.AuthError):
        auth.login("ann@example.com", "attacker password")


def test_disabled_account_gets_the_disabled_message_from_google(env, monkeypatch):
    existing = auth.register("ann@example.com", "correct horse")
    with db.connection() as c:
        c.execute("UPDATE users SET disabled_at = ?, google_sub = 'g-1' WHERE id = ?", (db.now(), existing.id))
    _fake_google(monkeypatch, PROFILE)
    state = _start(env)
    r = env.get(f"/api/auth/google/callback?code=abc&state={state}")
    assert r.headers["location"] == "/#/login?error=account_disabled"


def test_token_endpoint_failure(env, monkeypatch):
    _fake_google(monkeypatch, PROFILE, token_status=400)
    state = _start(env)
    r = env.get(f"/api/auth/google/callback?code=bad&state={state}")
    assert r.headers["location"] == "/#/login?error=google_failed"


def test_frontend_url_override(env, monkeypatch):
    monkeypatch.setenv("STUDIO_FRONTEND_URL", "https://app.example.com/")
    r = env.get("/api/auth/google/callback?error=access_denied")
    assert r.headers["location"] == "https://app.example.com/#/login?error=google_denied"


def test_google_only_account_cannot_password_login_and_can_set_one(env):
    user = auth.login_with_google("g-9", "solo@example.com", "Solo")
    with pytest.raises(auth.AuthError):
        auth.login("solo@example.com", "")
    with pytest.raises(auth.AuthError):
        auth.login("solo@example.com", "anything at all")
    updated = auth.change_password(user.id, "", "brand new password")   # no current password needed
    assert updated.has_password
    assert auth.login("solo@example.com", "brand new password").id == user.id


def test_google_only_account_deletes_by_typing_its_email(env):
    user = auth.login_with_google("g-9", "solo@example.com", "Solo")
    with pytest.raises(auth.AuthError):
        auth.delete_account(user.id, "wrong@example.com")
    auth.delete_account(user.id, " Solo@Example.com ")
    assert auth.get(user.id) is None
