"""studio: email verification, password reset, receipts, low-credit alerts and the admin console.

No SMTP server and no network: ``mailer._deliver`` is replaced by a list. Each test has its
own database.
"""
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio import admin, auth, credits, db, lifecycle, lifecycle_api, mailer, plans
from studio.payments import service


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_DB_PATH", str(tmp_path / "studio.db"))
    monkeypatch.setenv("STUDIO_SECRET", "test-secret")
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("STUDIO_PAID", "1")
    monkeypatch.setenv("ADMIN_EMAILS", "boss@example.com")
    monkeypatch.setenv("FRONTEND_URL", "https://app.test")
    monkeypatch.delenv("REQUIRE_VERIFIED_EMAIL", raising=False)
    sent = []
    monkeypatch.setattr(mailer, "_deliver", lambda msg: sent.append(msg))
    monkeypatch.setattr(mailer, "SYNC", True)
    db._initialised_for = None
    auth.clear_all_throttles()
    db.init()
    return sent


def _user(email="a@example.com", verified=False):
    u = auth.register(email, "correct horse", "Ann")
    if verified:
        _verify_sql(u.id)
    return auth.get(u.id)


def _verify_sql(uid):
    with db.connection() as c:
        c.execute("UPDATE users SET email_verified_at = ? WHERE id = ?", (db.now(), uid))


def _token_in(msg, kind):
    body = msg.get_body(preferencelist=("plain",)).get_content()
    m = re.search(rf"#/{kind}\?token=([\w-]+)", body)
    assert m, body
    return m.group(1)


# ---- verify email ------------------------------------------------------------------------------
def test_verification_email_confirms_once_and_releases_the_free_credits(env):
    u = _user()
    assert credits.balance(u.id)["remaining"] == 0            # withheld until the inbox is proven
    assert lifecycle.send_verification(u.id) is True
    assert len(env) == 1 and env[0]["To"] == "a@example.com"
    token = _token_in(env[0], "verify")

    verified = lifecycle.verify_email(token)
    assert verified.email_verified is True
    assert credits.balance(u.id)["remaining"] == plans.get_plan("free").credits
    with pytest.raises(auth.AuthError) as e:                  # single use
        lifecycle.verify_email(token)
    assert e.value.code == "invalid_token"
    assert lifecycle.send_verification(u.id) is False         # nothing left to confirm


def test_without_smtp_nothing_is_required_and_free_credits_flow(env, monkeypatch):
    monkeypatch.delenv("SMTP_HOST")
    u = _user()
    assert lifecycle.send_verification(u.id) is False and env == []
    assert credits.balance(u.id)["remaining"] == plans.get_plan("free").credits


def test_garbage_and_expired_tokens_are_refused(env):
    u = _user()
    with pytest.raises(auth.AuthError):
        lifecycle.verify_email("nope")
    token = lifecycle.create_token(u.id, "verify", ttl=-1)
    with pytest.raises(auth.AuthError):
        lifecycle.verify_email(token)
    # a token of one kind never works as another
    reset = lifecycle.create_token(u.id, "reset", ttl=600)
    with pytest.raises(auth.AuthError):
        lifecycle.verify_email(reset)


def test_a_new_token_kills_the_previous_one(env):
    u = _user()
    old = lifecycle.create_token(u.id, "verify", 600)
    lifecycle.create_token(u.id, "verify", 600)
    with pytest.raises(auth.AuthError):
        lifecycle.verify_email(old)


# ---- reset password ----------------------------------------------------------------------------
def test_reset_changes_the_password_signs_everyone_out_and_is_single_use(env):
    u = _user(verified=True)
    old_token = auth.issue_token(u)
    lifecycle.request_reset("A@Example.com")
    token = _token_in(env[0], "reset")

    with pytest.raises(auth.AuthError) as weak:               # a refused password keeps the link alive
        lifecycle.reset_password(token, "short")
    assert weak.value.code == "weak_password"

    updated = lifecycle.reset_password(token, "a brand new passphrase")
    assert auth.user_from_token(old_token) is None            # old sessions are dead
    assert auth.login("a@example.com", "a brand new passphrase").id == u.id
    with pytest.raises(auth.AuthError):
        auth.login("a@example.com", "correct horse")
    with pytest.raises(auth.AuthError):
        lifecycle.reset_password(token, "another passphrase 2")
    assert updated.email_verified is True


def test_reset_request_never_reveals_who_has_an_account(env):
    _user()
    lifecycle.request_reset("ghost@example.com")              # no error, no email
    assert env == []
    lifecycle.request_reset("a@example.com")
    assert len(env) == 1


def test_reset_requests_are_throttled_per_address(env):
    _user()
    for _ in range(6):
        lifecycle.request_reset("a@example.com")
    assert len(env) == 3


def test_disabled_accounts_get_no_reset_link(env):
    u = _user()
    with db.connection() as c:
        c.execute("UPDATE users SET disabled_at = ? WHERE id = ?", (db.now(), u.id))
    lifecycle.request_reset("a@example.com")
    assert env == []


# ---- receipts and low credits ------------------------------------------------------------------
def _paid_topup(uid, ref="cs_1"):
    with db.write_connection() as c:
        granted = service.grant_topup(c, uid, "topup_100", f"stripe:topup:{ref}")
        service.record_payment(c, uid, "stripe", ref, "topup", "topup_100", 500, "usd", granted, "paid", db.now())


def test_receipt_is_sent_once_and_retried_after_a_mail_failure(env, monkeypatch):
    u = _user(verified=True)
    _paid_topup(u.id)
    monkeypatch.setattr(mailer, "_deliver", lambda m: (_ for _ in ()).throw(OSError("smtp down")))
    assert lifecycle.send_pending_receipts() == 0             # failed: not marked as sent
    monkeypatch.setattr(mailer, "_deliver", lambda m: env.append(m))
    assert lifecycle.send_pending_receipts() == 1
    assert lifecycle.send_pending_receipts() == 0             # idempotent
    assert len(env) == 1 and "$5.00" in env[0].get_body(preferencelist=("plain",)).get_content()


def test_low_credit_alert_is_sent_once_per_month(env):
    u = _user(verified=True)
    assert lifecycle.check_low_credits(u.id) is False         # plenty left
    credits.spend_up_to(u.id, "job-1", "process", 27)
    assert lifecycle.check_low_credits(u.id) is True
    assert lifecycle.check_low_credits(u.id) is False
    assert len(env) == 1


# ---- admin -------------------------------------------------------------------------------------
@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(lifecycle_api.build_router())
    app.include_router(admin.build_router())
    return TestClient(app)


def _h(user):
    return {"Authorization": f"Bearer {auth.issue_token(user)}"}


def test_only_a_verified_listed_email_is_admin(env):
    boss = _user("boss@example.com")                          # registered, inbox not proven
    assert boss.is_admin is False
    _verify_sql(boss.id)
    assert auth.get(boss.id).is_admin is True
    assert _user("other@example.com", verified=True).is_admin is False


def test_admin_routes_are_invisible_to_everyone_else(client, env):
    normal = _user("n@example.com", verified=True)
    assert client.get("/api/admin/overview").status_code == 401
    assert client.get("/api/admin/overview", headers=_h(normal)).status_code == 404


def test_overview_users_and_audit(client, env):
    boss = _user("boss@example.com", verified=True)
    u = _user(verified=True)
    _paid_topup(u.id)
    h = _h(boss)

    ov = client.get("/api/admin/overview", headers=h).json()
    assert ov["users"]["total"] == 2 and ov["revenue"]["usd"]["total"] == 500
    assert ov["mail_enabled"] is True

    found = client.get("/api/admin/users", params={"q": "a@exam"}, headers=h).json()
    assert [x["email"] for x in found["users"]] == ["a@example.com"]
    assert found["users"][0]["credits_left"] == 100           # the top-up; the free month is granted lazily

    detail = client.get(f"/api/admin/users/{u.id}", headers=h).json()
    assert detail["payments"][0]["status"] == "paid"

    assert client.post(f"/api/admin/users/{u.id}/grant", json={"credits": 50, "note": "sorry"}, headers=h).status_code == 200
    assert credits.balance(u.id)["remaining"] == 180
    assert client.post(f"/api/admin/users/{u.id}/grant", json={"credits": 0}, headers=h).status_code == 422
    log = client.get("/api/admin/audit", headers=h).json()["entries"]
    assert log[0]["action"] == "grant" and log[0]["admin_email"] == "boss@example.com"
    assert log[0]["detail"]["credits"] == 50


def test_disabling_locks_the_account_at_once(client, env):
    boss = _user("boss@example.com", verified=True)
    u = _user(verified=True)
    token = auth.issue_token(u)
    h = _h(boss)
    assert client.post(f"/api/admin/users/{boss.id}/disable", headers=h).status_code == 400   # not yourself
    assert client.post(f"/api/admin/users/{u.id}/disable", headers=h).status_code == 200
    assert auth.user_from_token(token) is None
    with pytest.raises(auth.AuthError) as e:
        auth.login("a@example.com", "correct horse")
    assert e.value.code == "account_disabled"
    client.post(f"/api/admin/users/{u.id}/enable", headers=h)
    assert auth.login("a@example.com", "correct horse").id == u.id


def test_refund_takes_back_unspent_credits_once(client, env):
    boss = _user("boss@example.com", verified=True)
    u = _user(verified=True)
    _paid_topup(u.id)
    credits.spend_up_to(u.id, "j", "process", 40)             # uses the free credits first
    with db.connection() as c:
        pid = c.execute("SELECT id FROM payments").fetchone()["id"]
    h = _h(boss)

    res = client.post(f"/api/admin/payments/{pid}/refund", json={"note": "asked"}, headers=h).json()
    assert res["refunded"] is True and res["clawed_back"] > 0
    assert credits.balance(u.id)["topup_remaining"] == 0
    assert client.post(f"/api/admin/payments/{pid}/refund", json={}, headers=h).status_code == 409


def test_refunding_a_plan_payment_returns_the_user_to_free(client, env):
    boss = _user("boss@example.com", verified=True)
    u = _user(verified=True)
    with db.write_connection() as c:
        end = db.now() + 20 * 86400
        service.upsert_subscription(c, u.id, "payos", "o1", "starter", "active", db.now(), end)
        service.grant_period_credits(c, u.id, "starter", "payos:order:o1", end)
        service.refresh_user_plan(c, u.id)
        service.record_payment(c, u.id, "payos", "o1", "subscription", "starter", 299000, "vnd", 300, "paid", db.now())
    assert auth.get(u.id).plan == "starter"
    with db.connection() as c:
        pid = c.execute("SELECT id FROM payments").fetchone()["id"]
    out = client.post(f"/api/admin/payments/{pid}/refund", json={}, headers=_h(boss)).json()
    assert out["plan"] == "free" and auth.get(u.id).plan == "free"


# ---- HTTP: forgot / reset / verify / resend ----------------------------------------------------
def test_http_flow_forgot_reset_verify_resend(client, env):
    u = _user()
    assert client.post("/api/auth/forgot", json={"email": "a@example.com"}).json() == {"ok": True}
    token = _token_in(env[-1], "reset")
    out = client.post("/api/auth/reset", json={"token": token, "password": "yet another passphrase"})
    assert out.status_code == 200 and out.json()["user"]["email_verified"] is True
    assert client.post("/api/auth/reset", json={"token": token, "password": "yet another passphrase"}).status_code == 400

    other = _user("b@example.com")
    h = _h(other)
    assert client.post("/api/me/verify/resend", headers=h).json() == {"sent": True}
    vt = _token_in(env[-1], "verify")
    assert client.post("/api/auth/verify", json={"token": vt}).json()["verified"] is True
    assert client.post("/api/me/verify/resend", headers=h).json()["reason"] == "already_verified"
    assert u.id != other.id
