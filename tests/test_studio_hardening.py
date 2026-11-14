"""Money and security fixes: persistent throttles, sign-up abuse, account deletion with a live
subscription, refund / dispute webhooks, a second subscription, and the production switches."""
import hashlib
import hmac
import json

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from studio import api, auth, credits, db, emailnorm, security
from studio.payments import api as payments_api
from studio.payments import service, stripe_provider

WEBHOOK_SECRET = "whsec_test"


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_DB_PATH", str(tmp_path / "studio.db"))
    monkeypatch.setenv("STUDIO_SECRET", "test-secret")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    db._initialised_for = None
    auth.clear_all_throttles()
    db.init()
    yield


@pytest.fixture
def client():
    ctx = api.Context(job_status=lambda j: None, cancel_job=lambda j: False, remove_job_files=lambda j: None)
    app = FastAPI()
    app.include_router(api.build_router(ctx))
    app.include_router(payments_api.build_router())
    return TestClient(app)


def _user(email="a@example.com"):
    return auth.register(email, "correct horse", "Ann")


def _headers(user):
    return {"Authorization": f"Bearer {auth.issue_token(user)}"}


# ---- throttles -------------------------------------------------------------------------------
def test_throttle_lives_in_the_database_so_a_restart_does_not_reset_it():
    for _ in range(3):
        auth.throttle("t:x", 3, 600)
    db._initialised_for = None                    # what a process restart amounts to
    with pytest.raises(auth.AuthError) as e:
        auth.throttle("t:x", 3, 600)
    assert e.value.status == 429
    auth.throttle("t:other", 3, 600)              # another bucket is unaffected


def test_throttle_window_expires():
    with db.connection() as c:
        c.execute("INSERT INTO rate_hits (bucket, at) VALUES ('t:old', ?)", (db.now() - 7200,))
    auth.throttle("t:old", 1, 600)                # the only earlier hit is outside the window


def test_login_is_also_limited_per_address_across_many_ips():
    _user()
    for i in range(30):
        with pytest.raises(auth.AuthError) as e:
            auth.login("a@example.com", "wrong password", client_ip=f"10.0.0.{i}")
        assert e.value.code == "bad_credentials"
    with pytest.raises(auth.AuthError) as e:      # 31st guess from yet another address
        auth.login("a@example.com", "wrong password", client_ip="10.9.9.9")
    assert e.value.code == "too_many_attempts"


def test_current_password_guessing_is_limited_for_a_stolen_token():
    u = _user()
    for _ in range(8):
        with pytest.raises(auth.AuthError) as e:
            auth.change_password(u.id, "nope nope nope", "another good one")
        assert e.value.code == "bad_credentials"
    with pytest.raises(auth.AuthError) as e:
        auth.change_password(u.id, "correct horse", "another good one")   # even the right one now waits
    assert e.value.code == "too_many_attempts"


def test_purge_removes_only_old_hits():
    auth.throttle("t:fresh", 5, 600)
    with db.connection() as c:
        c.execute("INSERT INTO rate_hits (bucket, at) VALUES ('t:ancient', ?)", (db.now() - 3 * 86400,))
    assert auth.purge_old_throttles() == 1


# ---- sign-up abuse ---------------------------------------------------------------------------
def test_gmail_dots_and_plus_tags_are_one_inbox():
    assert emailnorm.canonical("A.B.C+promo@Gmail.com") == "abc@gmail.com"
    assert emailnorm.canonical("x+y@example.com") == "x@example.com"
    assert emailnorm.canonical("a.b@example.com") == "a.b@example.com"     # dots only fold on Gmail
    auth.register("jane.doe@gmail.com", "correct horse")
    for alias in ("janedoe@gmail.com", "jane.doe+free2@gmail.com", "j.a.n.e.d.o.e@googlemail.com"):
        with pytest.raises(auth.AuthError) as e:
            auth.register(alias, "correct horse")
        assert e.value.code == "email_taken"


def test_disposable_domains_are_refused(monkeypatch):
    with pytest.raises(auth.AuthError) as e:
        auth.register("x@mailinator.com", "correct horse")
    assert e.value.code == "disposable_email"
    monkeypatch.setenv("BLOCKED_EMAIL_DOMAINS", "burner.test, other.test")
    with pytest.raises(auth.AuthError):
        auth.register("x@burner.test", "correct horse")


def test_terms_acceptance_is_recorded():
    u = auth.register("t@example.com", "correct horse", tos_version="2026-11")
    with db.connection() as c:
        row = c.execute("SELECT tos_accepted_at, tos_version FROM users WHERE id = ?", (u.id,)).fetchone()
    assert row["tos_version"] == "2026-11" and row["tos_accepted_at"]


def test_existing_accounts_get_a_canonical_address_on_upgrade():
    with db.connection() as c:
        c.execute("INSERT INTO users (email, name, password_hash, created_at) VALUES "
                  "('Old.User+x@gmail.com', 'o', 'x', 1)")
        c.execute("UPDATE users SET email_canonical = NULL")
    db._initialised_for = None
    db.init()
    with db.connection() as c:
        got = c.execute("SELECT email_canonical FROM users WHERE name = 'o'").fetchone()[0]
    assert got == "olduser@gmail.com"


# ---- account deletion with a live subscription ----------------------------------------------
def _subscribe(user, provider="stripe", ref="sub_1", plan="starter"):
    with db.write_connection() as c:
        end = db.now() + 20 * 86400
        service.upsert_subscription(c, user.id, provider, ref, plan, "active", db.now(), end)
        service.refresh_user_plan(c, user.id)
        service.record_payment(c, user.id, provider, "in_1", "subscription", plan, 1200, "usd", 300,
                               "paid", db.now())


def test_deleting_an_account_cancels_the_card_subscription_and_keeps_the_payment_record(client, monkeypatch):
    u = _user()
    _subscribe(u)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test")
    cancelled = []
    monkeypatch.setattr(stripe_provider, "cancel_subscription", lambda sid: cancelled.append(sid))
    r = client.request("DELETE", "/api/me", json={"password": "correct horse"}, headers=_headers(u))
    assert r.status_code == 200 and cancelled == ["sub_1"]
    assert auth.get(u.id) is None
    with db.connection() as c:
        records = c.execute("SELECT provider_ref, amount, status FROM payment_records").fetchall()
        assert c.execute("SELECT COUNT(*) FROM payments").fetchone()[0] == 0     # the cascade did run
    assert [(r["provider_ref"], r["amount"], r["status"]) for r in records] == [("in_1", 1200, "paid")]


def test_account_is_kept_when_the_subscription_cannot_be_cancelled(client, monkeypatch):
    u = _user()
    _subscribe(u)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test")

    def boom(_):
        raise stripe_provider.StripeError("down")
    monkeypatch.setattr(stripe_provider, "cancel_subscription", boom)
    r = client.request("DELETE", "/api/me", json={"password": "correct horse"}, headers=_headers(u))
    assert r.status_code == 502 and r.json()["detail"]["error"] == "cancel_failed"
    assert auth.get(u.id) is not None


def test_a_wrong_password_cancels_nothing(client, monkeypatch):
    u = _user()
    _subscribe(u)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test")
    cancelled = []
    monkeypatch.setattr(stripe_provider, "cancel_subscription", lambda sid: cancelled.append(sid))
    r = client.request("DELETE", "/api/me", json={"password": "not it"}, headers=_headers(u))
    assert r.status_code == 401 and cancelled == []


# ---- a second subscription -------------------------------------------------------------------
def test_a_card_subscriber_cannot_start_another_plan(client, monkeypatch):
    u = _user()
    _subscribe(u)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test")
    r = client.post("/api/billing/checkout", json={"kind": "subscription", "item": "pro", "provider": "stripe"},
                    headers=_headers(u))
    assert r.status_code == 409 and r.json()["detail"]["error"] == "already_subscribed"


def test_topups_are_always_allowed(client, monkeypatch):
    u = _user()
    _subscribe(u)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(stripe_provider, "create_checkout",
                        lambda *a, **k: {"id": "cs_1", "url": "https://stripe.test/pay"})
    r = client.post("/api/billing/checkout", json={"kind": "topup", "item": "topup_100", "provider": "stripe"},
                    headers=_headers(u))
    assert r.status_code == 200


def test_prepaid_plan_rules():
    u = _user()
    assert service.subscription_conflict(u.id, "payos", "starter") is None          # nothing active
    _subscribe(u, provider="payos", ref="order:1", plan="pro")
    assert service.subscription_conflict(u.id, "payos", "pro") is None              # renew queues the next period
    assert service.subscription_conflict(u.id, "payos", "starter")[0] == "downgrade_blocked"
    assert service.subscription_conflict(u.id, "stripe", "pro")[0] == "already_subscribed"
    v = _user("v@example.com")
    _subscribe(v, provider="payos", ref="order:2", plan="starter")
    assert service.subscription_conflict(v.id, "payos", "pro") is None              # going up is fine


# ---- Stripe: refunds, disputes, ordering ----------------------------------------------------
def _paid_card_user():
    u = _user()
    checkout = {"id": "evt_co", "type": "checkout.session.completed", "data": {"object": {
        "id": "cs_1", "mode": "subscription", "customer": "cus_1", "subscription": "sub_1",
        "client_reference_id": str(u.id),
        "metadata": {"user_id": str(u.id), "kind": "subscription", "item": "starter"}}}}
    invoice = {"id": "evt_in", "type": "invoice.paid", "data": {"object": {
        "id": "in_1", "subscription": "sub_1", "customer": "cus_1", "amount_paid": 1200, "currency": "usd",
        "payment_intent": "pi_1",
        "lines": {"data": [{"period": {"start": 1_700_000_000, "end": 1_700_000_000 + 30 * 86400}}]}}}}
    # periods in the past would lapse at once: stretch them to now
    now = int(db.now())
    invoice["data"]["object"]["lines"]["data"][0]["period"] = {"start": now, "end": now + 30 * 86400}
    assert stripe_provider.handle_event(checkout) == "applied"
    assert stripe_provider.handle_event(invoice) == "applied"
    assert auth.get(u.id).plan == "starter"
    return u


def _refund_event(**over):
    obj = {"id": "ch_1", "payment_intent": "pi_1", "invoice": "in_1", "amount": 1200,
           "amount_refunded": 1200, "refunded": True}
    obj.update(over)
    return {"id": over.pop("event_id", "evt_ref"), "type": "charge.refunded", "data": {"object": obj}}


def test_full_refund_takes_back_credits_ends_the_plan_and_cancels_at_stripe(monkeypatch):
    u = _paid_card_user()
    cancelled = []
    monkeypatch.setattr(stripe_provider, "cancel_subscription", lambda sid: cancelled.append(sid))
    assert stripe_provider.handle_event(_refund_event()) == "applied"
    assert auth.get(u.id).plan == "free"
    assert credits.balance(u.id)["plan_total"] == 0 or credits.balance(u.id)["remaining"] <= 30
    assert cancelled == ["sub_1"]
    with db.connection() as c:
        assert c.execute("SELECT status FROM payments WHERE provider_ref = 'in_1'").fetchone()[0] == "refunded"
    assert stripe_provider.handle_event(_refund_event()) == "duplicate"           # a Stripe retry


def test_refunding_a_topup_takes_back_its_unspent_credits():
    u = _user()
    ev = {"id": "evt_top", "type": "checkout.session.completed", "data": {"object": {
        "id": "cs_top", "mode": "payment", "payment_status": "paid", "payment_intent": "pi_top",
        "client_reference_id": str(u.id), "amount_total": 500, "currency": "usd",
        "metadata": {"user_id": str(u.id), "kind": "topup", "item": "topup_100"}}}}
    assert stripe_provider.handle_event(ev) == "applied"
    assert credits.balance(u.id)["topup_remaining"] == 100
    refund = {"id": "evt_rt", "type": "charge.refunded", "data": {"object": {
        "id": "ch_top", "payment_intent": "pi_top", "amount": 500, "amount_refunded": 500, "refunded": True}}}
    assert stripe_provider.handle_event(refund) == "applied"
    assert credits.balance(u.id)["topup_remaining"] == 0


def test_a_partial_refund_is_left_to_a_person():
    u = _paid_card_user()
    assert stripe_provider.handle_event(_refund_event(amount_refunded=300, refunded=False)) == "ignored"
    assert auth.get(u.id).plan == "starter"


def test_a_dispute_reverses_the_payment_like_a_refund(monkeypatch):
    u = _paid_card_user()
    monkeypatch.setattr(stripe_provider, "cancel_subscription", lambda sid: None)
    dispute = {"id": "evt_dp", "type": "charge.dispute.created",
               "data": {"object": {"id": "dp_1", "charge": "ch_1", "payment_intent": "pi_1"}}}
    assert stripe_provider.handle_event(dispute) == "applied"
    assert auth.get(u.id).plan == "free"
    with db.connection() as c:
        assert c.execute("SELECT status FROM payments WHERE provider_ref = 'in_1'").fetchone()[0] == "disputed"


def test_a_refund_for_an_unknown_charge_is_ignored():
    _paid_card_user()
    assert stripe_provider.handle_event(_refund_event(id="ch_x", payment_intent="pi_x", invoice="in_x")) == "ignored"


def test_a_late_paid_invoice_does_not_revive_a_cancelled_subscription(monkeypatch):
    u = _paid_card_user()
    monkeypatch.setattr(stripe_provider, "cancel_subscription", lambda sid: None)
    stripe_provider.handle_event(_refund_event())
    now = int(db.now())
    later = {"id": "evt_in2", "type": "invoice.paid", "data": {"object": {
        "id": "in_2", "subscription": "sub_1", "customer": "cus_1", "amount_paid": 1200, "currency": "usd",
        "lines": {"data": [{"period": {"start": now, "end": now + 30 * 86400}}]}}}}
    assert stripe_provider.handle_event(later) == "ignored"
    assert auth.get(u.id).plan == "free"


def test_an_invoice_whose_plan_is_not_known_yet_is_retried_not_lost():
    u = _user()
    now = int(db.now())
    ev = {"id": "evt_early", "type": "invoice.paid", "data": {"object": {
        "id": "in_9", "subscription": "sub_9", "customer": "cus_9", "amount_paid": 1200, "currency": "usd",
        "metadata": {"user_id": str(u.id)},
        "lines": {"data": [{"period": {"start": now, "end": now + 30 * 86400}}]}}}}
    with pytest.raises(service.UnknownUser):
        stripe_provider.handle_event(ev)
    with db.connection() as c:                    # the claim rolled back, so the retry is not a duplicate
        assert c.execute("SELECT COUNT(*) FROM payment_events WHERE event_id = 'evt_early'").fetchone()[0] == 0


def test_an_invoice_without_a_subscription_is_ignored():
    u = _user()
    ev = {"id": "evt_one", "type": "invoice.paid", "data": {"object": {
        "id": "in_one", "customer": "cus_1", "amount_paid": 500, "currency": "usd",
        "metadata": {"user_id": str(u.id)}}}}
    assert stripe_provider.handle_event(ev) == "ignored"


def test_admin_refund_also_cancels_the_card_subscription(monkeypatch):
    from studio import admin
    u = _paid_card_user()
    boss = _user("boss@example.com")
    cancelled = []
    monkeypatch.setattr(stripe_provider, "cancel_subscription", lambda sid: cancelled.append(sid))
    with db.connection() as c:
        pid = c.execute("SELECT id FROM payments WHERE provider_ref = 'in_1'").fetchone()["id"]
    out = admin.refund_payment(boss.id, pid, "customer asked")
    assert out["refunded"] and out["provider_cancel_failed"] == [] and cancelled == ["sub_1"]
    assert auth.get(u.id).plan == "free"


def test_admin_refund_reports_a_subscription_it_could_not_cancel(monkeypatch):
    from studio import admin
    _paid_card_user()
    boss = _user("boss@example.com")

    def boom(_):
        raise stripe_provider.StripeError("down")
    monkeypatch.setattr(stripe_provider, "cancel_subscription", boom)
    with db.connection() as c:
        pid = c.execute("SELECT id FROM payments WHERE provider_ref = 'in_1'").fetchone()["id"]
    out = admin.refund_payment(boss.id, pid, "")
    assert out["refunded"] and out["provider_cancel_failed"] == ["sub_1"]


# ---- webhooks --------------------------------------------------------------------------------
def test_a_flood_of_bad_signatures_is_slowed_down(client):
    body = json.dumps({"id": "evt_x", "type": "x"})
    codes = [client.post("/api/stripe/webhook", content=body, headers={"stripe-signature": "t=1,v1=00"}).status_code
             for _ in range(62)]
    assert codes[0] == 400 and codes[-1] == 429


def test_a_correct_signature_is_not_throttled(client):
    payload = json.dumps({"id": "evt_ok", "type": "unrelated"}).encode()
    import time
    t = int(time.time())
    sig = hmac.new(WEBHOOK_SECRET.encode(), f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
    r = client.post("/api/stripe/webhook", content=payload, headers={"stripe-signature": f"t={t},v1={sig}"})
    assert r.status_code == 200


# ---- production switches ---------------------------------------------------------------------
def test_production_refuses_a_weak_session_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    for weak in ("", "short", "secret", "test-secret"):
        monkeypatch.setenv("STUDIO_SECRET", weak)
        with pytest.raises(RuntimeError):
            security.check_production_config()
    monkeypatch.setenv("STUDIO_SECRET", "a" * 40)
    security.check_production_config()                  # a long secret starts fine


def test_outside_production_nothing_is_enforced(monkeypatch):
    monkeypatch.setenv("STUDIO_SECRET", "x")
    security.check_production_config()
