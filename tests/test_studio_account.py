"""Account features: terms acceptance, sign out everywhere, data export, change of email,
password-changed notice, API keys (and their use on the MCP endpoint)."""
import re

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from studio import api, apikeys, auth, db, lifecycle, lifecycle_api, mailer


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_DB_PATH", str(tmp_path / "studio.db"))
    monkeypatch.setenv("STUDIO_SECRET", "test-secret")
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("FRONTEND_URL", "https://app.test")
    monkeypatch.delenv("REQUIRE_TERMS", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("STUDIO_PAID", raising=False)
    sent = []
    monkeypatch.setattr(mailer, "_deliver", lambda msg: sent.append(msg))
    monkeypatch.setattr(mailer, "SYNC", True)
    db._initialised_for = None
    auth.clear_all_throttles()
    db.init()
    return sent


@pytest.fixture
def client():
    ctx = api.Context(job_status=lambda j: None, cancel_job=lambda j: False, remove_job_files=lambda j: None)
    app = FastAPI()
    app.include_router(api.build_router(ctx))
    app.include_router(lifecycle_api.build_router())
    return TestClient(app)


def _register(client, email="a@example.com", **extra):
    r = client.post("/api/auth/register", json={"email": email, "password": "correct horse", "name": "Ann", **extra})
    assert r.status_code == 200, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user"], body["token"]


# ---- terms -----------------------------------------------------------------------------------
def test_terms_are_optional_in_development_and_recorded_when_given(client):
    _register(client, "dev@example.com")                                   # no acceptance, no complaint
    _register(client, "yes@example.com", accept_terms=True)
    with db.connection() as c:
        rows = {r["email"]: r for r in c.execute("SELECT email, tos_accepted_at, tos_version FROM users")}
    assert rows["dev@example.com"]["tos_accepted_at"] is None
    assert rows["yes@example.com"]["tos_version"] == auth.terms_version()


def test_terms_are_required_in_production(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    r = client.post("/api/auth/register", json={"email": "p@example.com", "password": "correct horse"})
    assert r.status_code == 422 and r.json()["detail"]["error"] == "terms_required"
    ok = client.post("/api/auth/register", json={"email": "p@example.com", "password": "correct horse",
                                                 "accept_terms": True})
    assert ok.status_code == 200


def test_require_terms_can_be_switched_off_explicitly(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("REQUIRE_TERMS", "0")
    assert client.post("/api/auth/register",
                       json={"email": "q@example.com", "password": "correct horse"}).status_code == 200


def test_common_passwords_are_refused(client):
    for bad in ("password123", "12345678", "aaaaaaaaa", "Password123"):
        r = client.post("/api/auth/register", json={"email": "c@example.com", "password": bad})
        assert r.status_code == 422, bad
    assert client.post("/api/auth/register",
                       json={"email": "c@example.com", "password": "x" * 129}).json()["detail"]["error"] == "password_too_long"


# ---- sign out everywhere -----------------------------------------------------------------------
def test_logout_all_revokes_every_other_session(client):
    headers, _, old = _register(client)
    other_device = client.post("/api/auth/login", json={"email": "a@example.com", "password": "correct horse"}).json()["token"]
    r = client.post("/api/me/logout-all", headers=headers)
    assert r.status_code == 200
    fresh = r.json()["token"]
    assert client.get("/api/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401
    assert client.get("/api/me", headers={"Authorization": f"Bearer {other_device}"}).status_code == 401
    assert client.get("/api/me", headers={"Authorization": f"Bearer {fresh}"}).status_code == 200


# ---- password changed notice ------------------------------------------------------------------
def test_changing_the_password_tells_the_owner(client, env):
    headers, _, _ = _register(client)
    env.clear()
    r = client.post("/api/me/password", json={"current": "correct horse", "new": "another good one"}, headers=headers)
    assert r.status_code == 200
    assert len(env) == 1 and env[0]["To"] == "a@example.com"


# ---- data export --------------------------------------------------------------------------------
def test_export_contains_the_account_and_no_secrets(client):
    headers, user, _ = _register(client)
    r = client.get("/api/me/export", headers=headers)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    data = r.json()
    assert data["profile"]["email"] == "a@example.com" and data["profile"]["id"] == user["id"]
    text = r.text
    assert "scrypt" not in text and "password_hash" not in text and "key_hash" not in text
    assert set(data) >= {"projects", "brand_kits", "payments", "credit_ledger", "api_keys"}


def test_export_needs_a_signed_in_person(client):
    assert client.get("/api/me/export").status_code == 401


# ---- change email ---------------------------------------------------------------------------------
def _link_token(msg):
    body = msg.get_body(preferencelist=("plain",)).get_content()
    return re.search(r"#/verify\?token=([\w-]+)", body).group(1)


def test_email_change_needs_the_password_then_the_link_from_the_new_inbox(client, env):
    headers, user, _ = _register(client)
    env.clear()
    wrong = client.post("/api/me/email", json={"email": "new@example.com", "password": "nope nope nope"}, headers=headers)
    assert wrong.status_code == 401 and env == []
    ok = client.post("/api/me/email", json={"email": "New@Example.com", "password": "correct horse"}, headers=headers)
    assert ok.status_code == 200
    assert len(env) == 1 and env[0]["To"] == "new@example.com"            # the link goes to the NEW address
    assert auth.get(user["id"]).email == "a@example.com"                  # nothing changed yet
    token = _link_token(env[0])
    env.clear()
    confirmed = client.post("/api/auth/verify", json={"token": token})
    assert confirmed.status_code == 200
    changed = auth.get(user["id"])
    assert changed.email == "new@example.com" and changed.email_verified
    assert [m["To"] for m in env] == ["a@example.com"]                    # the old address is told
    assert client.get("/api/me", headers=headers).status_code == 401       # signed out everywhere
    assert client.post("/api/auth/login", json={"email": "new@example.com", "password": "correct horse"}).status_code == 200


def test_email_change_refuses_taken_same_and_throwaway_addresses(client):
    headers, _, _ = _register(client)
    _register(client, "taken@example.com")
    for addr, code in (("taken@example.com", "email_taken"), ("a@example.com", "same_email"),
                       ("x@mailinator.com", "disposable_email")):
        r = client.post("/api/me/email", json={"email": addr, "password": "correct horse"}, headers=headers)
        assert r.json()["detail"]["error"] == code, addr


def test_email_change_link_is_single_use_and_checks_the_address_again(client, env):
    headers, user, _ = _register(client)
    client.post("/api/me/email", json={"email": "new@example.com", "password": "correct horse"}, headers=headers)
    token = _link_token(env[-1])
    _register(client, "new@example.com")                                  # someone takes it meanwhile
    r = client.post("/api/auth/verify", json={"token": token})
    assert r.status_code == 409 and auth.get(user["id"]).email == "a@example.com"


def test_email_change_without_mail_is_refused(client, monkeypatch):
    headers, _, _ = _register(client)
    monkeypatch.delenv("SMTP_HOST")
    r = client.post("/api/me/email", json={"email": "new@example.com", "password": "correct horse"}, headers=headers)
    assert r.json()["detail"]["error"] == "mail_off"


# ---- resend verification without signing in ------------------------------------------------------
def test_public_resend_is_quiet_for_unknown_addresses(client, env):
    _register(client)
    env.clear()
    assert client.post("/api/auth/verify/resend", json={"email": "ghost@example.com"}).json() == {"ok": True}
    assert env == []
    assert client.post("/api/auth/verify/resend", json={"email": "a@example.com"}).json() == {"ok": True}
    assert len(env) == 1 and env[0]["To"] == "a@example.com"


# ---- API keys ---------------------------------------------------------------------------------------
def test_api_key_lifecycle(client):
    headers, user, _ = _register(client)
    created = client.post("/api/keys", json={"name": "n8n"}, headers=headers).json()
    assert created["key"].startswith("vsk_") and created["name"] == "n8n"
    listed = client.get("/api/keys", headers=headers).json()["items"]
    assert [k["id"] for k in listed] == [created["id"]] and "key" not in listed[0]
    with db.connection() as c:                                            # only the hash is stored
        assert created["key"] not in str(c.execute("SELECT * FROM api_keys").fetchall()[0][:])
    via_key = client.get("/api/me", headers={"Authorization": f"Bearer {created['key']}"})
    assert via_key.status_code == 200 and via_key.json()["user"]["id"] == user["id"]
    assert client.get("/api/keys", headers=headers).json()["items"][0]["last_used_at"]
    assert client.delete(f"/api/keys/{created['id']}", headers=headers).status_code == 200
    assert client.get("/api/me", headers={"Authorization": f"Bearer {created['key']}"}).status_code == 401
    assert client.delete(f"/api/keys/{created['id']}", headers=headers).status_code == 404


def test_a_key_cannot_manage_keys_or_export_data(client):
    headers, _, _ = _register(client)
    key = client.post("/api/keys", json={}, headers=headers).json()["key"]
    as_key = {"Authorization": f"Bearer {key}"}
    for method, path in (("get", "/api/keys"), ("post", "/api/keys"), ("get", "/api/me/export"),
                         ("post", "/api/me/logout-all")):
        r = getattr(client, method)(path, headers=as_key)
        assert r.status_code == 403 and r.json()["detail"]["error"] == "session_required", path


def test_keys_are_private_to_their_owner_and_capped(client):
    a, _, _ = _register(client)
    b, _, _ = _register(client, "b@example.com")
    key = client.post("/api/keys", json={}, headers=a).json()
    assert client.delete(f"/api/keys/{key['id']}", headers=b).status_code == 404
    for _ in range(apikeys.MAX_KEYS - 1):
        assert client.post("/api/keys", json={}, headers=a).status_code == 200
    assert client.post("/api/keys", json={}, headers=a).json()["detail"]["error"] == "too_many_keys"


def test_a_locked_account_and_its_keys_stop_working(client):
    headers, user, _ = _register(client)
    key = client.post("/api/keys", json={}, headers=headers).json()["key"]
    with db.connection() as c:
        c.execute("UPDATE users SET disabled_at = ? WHERE id = ?", (db.now(), user["id"]))
    assert client.get("/api/me", headers={"Authorization": f"Bearer {key}"}).status_code == 401


def test_keys_need_a_plan_with_api_access_in_paid_mode(client, monkeypatch):
    headers, user, _ = _register(client)
    key = client.post("/api/keys", json={}, headers=headers).json()["key"]
    monkeypatch.setenv("STUDIO_PAID", "1")
    r = client.post("/api/keys", json={}, headers=headers)                # free plan has no api_access
    assert r.status_code == 402 and r.json()["detail"]["feature"] == "api_access"
    assert client.get("/api/me", headers={"Authorization": f"Bearer {key}"}).status_code == 401   # key sleeps
    with db.connection() as c:
        c.execute("UPDATE users SET plan = 'pro' WHERE id = ?", (user["id"],))
    assert client.get("/api/me", headers={"Authorization": f"Bearer {key}"}).status_code == 200   # and wakes up
    assert client.post("/api/keys", json={}, headers=headers).status_code == 200


# ---- the MCP endpoint ------------------------------------------------------------------------------
def test_mcp_in_accounts_mode_needs_a_key_and_a_plan_with_api_access(monkeypatch):
    import mcp_server
    monkeypatch.setenv("ACCOUNTS_ENABLED", "1")
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    ctx = api.Context(job_status=lambda j: None, cancel_job=lambda j: False, remove_job_files=lambda j: None)
    app = FastAPI()
    app.include_router(api.build_router(ctx))
    app.include_router(mcp_server.router)
    c = TestClient(app)
    ping = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    assert c.post("/mcp", json=ping).status_code == 401                    # anonymous
    headers, user, _ = _register(c)
    key = c.post("/api/keys", json={}, headers=headers).json()["key"]
    assert c.post("/mcp", json=ping, headers={"Authorization": f"Bearer {key}"}).status_code == 200
    monkeypatch.setenv("STUDIO_PAID", "1")
    assert c.post("/mcp", json=ping, headers=headers).status_code == 402   # free plan: no API / agent access
    with db.connection() as conn:
        conn.execute("UPDATE users SET plan = 'pro' WHERE id = ?", (user["id"],))
    assert c.post("/mcp", json=ping, headers={"Authorization": f"Bearer {key}"}).status_code == 200
