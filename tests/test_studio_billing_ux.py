"""The billing surface a customer touches: cancel/resume, invoice details, receipts, promo codes,
and the plan-life emails. Providers are stubbed; each test gets its own database."""
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from studio import api, auth, credits, db, lifecycle, mailer, plans, promo
from studio.payments import api as payments_api
from studio.payments import service, stripe_provider


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_DB_PATH", str(tmp_path / "studio.db"))
    monkeypatch.setenv("STUDIO_SECRET", "test-secret")
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("FRONTEND_URL", "https://app.test")
    monkeypatch.setenv("COMPANY_NAME", "Test Co")
    monkeypatch.setenv("STUDIO_PAID", "1")
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
    app.include_router(payments_api.build_router())
    return TestClient(app)


def _register(client, email="a@example.com"):
    r = client.post("/api/auth/register", json={"email": email, "password": "correct horse", "name": "Ann"})
    assert r.status_code == 200, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user"]["id"]


def _paid(uid, ref="pi_1", amount=1200):
    with db.write_connection() as c:
        service.record_payment(c, uid, "stripe", ref, "topup", "topup_100", amount, "usd", 100, "paid",
                               paid_at=db.now())
    return service.payments_for_user(uid)[0]["id"]


def _stripe_sub(uid, ref="sub_1", status="active", end=None, provider="stripe"):
    with db.write_connection() as c:
        c.execute("INSERT INTO subscriptions (user_id, provider, provider_ref, plan, status, current_period_start, "
                  "current_period_end, cancel_at_period_end, created_at, updated_at) VALUES (?,?,?,?,?,?,?,0,?,?)",
                  (uid, provider, ref, "starter", status, db.now() - 100, end or db.now() + 86400 * 20,
                   db.now(), db.now()))


# ---- cancel / resume -------------------------------------------------------------------------
def test_cancel_and_resume_a_card_subscription(client, monkeypatch):
    h, uid = _register(client)
    _stripe_sub(uid)
    calls = []
    monkeypatch.setattr(stripe_provider, "configured", lambda: True)
    monkeypatch.setattr(stripe_provider, "set_cancel_at_period_end", lambda ref, flag: calls.append((ref, flag)))
    assert client.post("/api/billing/cancel", headers=h).json() == {"cancel_at_period_end": True}
    assert client.get("/api/billing/status", headers=h).json()["subscription"]["cancel_at_period_end"] is True
    assert client.post("/api/billing/resume", headers=h).json() == {"cancel_at_period_end": False}
    assert calls == [("sub_1", True), ("sub_1", False)]
    assert client.get("/api/billing/status", headers=h).json()["subscription"]["cancel_at_period_end"] is False


def test_cancel_without_a_card_subscription_is_a_404(client, monkeypatch):
    h, _ = _register(client)
    monkeypatch.setattr(stripe_provider, "configured", lambda: True)
    assert client.post("/api/billing/cancel", headers=h).status_code == 404


def test_a_stripe_failure_leaves_the_flag_alone(client, monkeypatch):
    h, uid = _register(client)
    _stripe_sub(uid)
    monkeypatch.setattr(stripe_provider, "configured", lambda: True)

    def boom(ref, flag):
        raise stripe_provider.StripeError("down", 502)
    monkeypatch.setattr(stripe_provider, "set_cancel_at_period_end", boom)
    assert client.post("/api/billing/cancel", headers=h).status_code == 502
    assert client.get("/api/billing/status", headers=h).json()["subscription"]["cancel_at_period_end"] is False


# ---- invoice details and receipts ------------------------------------------------------------
def test_billing_info_roundtrip_and_validation(client):
    h, _ = _register(client)
    assert client.get("/api/billing/info", headers=h).json()["company"] == ""
    bad = client.put("/api/billing/info", headers=h, json={"company": "X", "tax_code": "12ab"})
    assert bad.status_code == 422 and bad.json()["detail"]["error"] == "bad_tax_code"
    ok = client.put("/api/billing/info", headers=h, json={"company": "ACME", "tax_code": "0312345678-001",
                                                          "address": "1 Street", "email": "ke@acme.vn"})
    assert ok.status_code == 200 and ok.json()["tax_code"] == "0312345678-001"
    assert client.get("/api/billing/info", headers=h).json()["company"] == "ACME"


def test_receipt_shows_buyer_and_seller_and_hides_other_peoples_payments(client):
    h1, u1 = _register(client, "one@example.com")
    h2, _ = _register(client, "two@example.com")
    pid = _paid(u1)
    r = client.get(f"/api/billing/payments/{pid}", headers=h1).json()
    assert r["payment"]["amount"] == 1200 and r["buyer"]["account_email"] == "one@example.com"
    assert r["seller"]["name"] == "Test Co"
    assert client.get(f"/api/billing/payments/{pid}", headers=h2).status_code == 404


def test_invoice_request_needs_company_details_and_a_paid_payment(client):
    h, uid = _register(client)
    pid = _paid(uid)
    r = client.post(f"/api/billing/payments/{pid}/invoice", headers=h)
    assert r.status_code == 422 and r.json()["detail"]["error"] == "billing_info_missing"
    client.put("/api/billing/info", headers=h, json={"company": "ACME", "tax_code": "0312345678"})
    assert client.post(f"/api/billing/payments/{pid}/invoice", headers=h).json() == {"ok": True}
    assert service.payments_for_user(uid)[0]["invoice_requested_at"]
    assert client.post("/api/billing/payments/999/invoice", headers=h).status_code == 404


# ---- promo codes -----------------------------------------------------------------------------
def test_promo_grants_credits_once_per_person(client):
    h1, u1 = _register(client, "one@example.com")
    h2, u2 = _register(client, "two@example.com")
    promo.create("WELCOME50", 50)
    before = credits.balance(u1)["topup_remaining"]
    r = client.post("/api/billing/redeem", headers=h1, json={"code": " WELCOME50 "})
    assert r.status_code == 200 and r.json()["credits"] == 50
    assert credits.balance(u1)["topup_remaining"] == before + 50
    again = client.post("/api/billing/redeem", headers=h1, json={"code": "WELCOME50"})
    assert again.status_code == 409 and again.json()["detail"]["error"] == "already_redeemed"
    assert client.post("/api/billing/redeem", headers=h2, json={"code": "WELCOME50"}).status_code == 200
    assert promo.get("WELCOME50")["used"] == 2


def test_unknown_expired_inactive_and_used_up_codes_look_the_same(client):
    h, _ = _register(client)
    promo.create("OLD", 10, expires_at=db.now() - 10)
    promo.create("OFF", 10)
    promo.set_active("OFF", False)
    promo.create("ONE", 10, max_uses=1)
    h2, _ = _register(client, "two@example.com")
    assert client.post("/api/billing/redeem", headers=h2, json={"code": "ONE"}).status_code == 200
    for code in ("NOPE", "OLD", "OFF", "ONE"):
        r = client.post("/api/billing/redeem", headers=h, json={"code": code})
        assert r.status_code == 404 and r.json()["detail"]["error"] == "invalid_code"


def test_promo_guessing_is_throttled(client):
    h, _ = _register(client)
    codes = [client.post("/api/billing/redeem", headers=h, json={"code": f"GUESS{i}"}).status_code
             for i in range(12)]
    assert codes[:10] == [404] * 10 and 429 in codes[10:]


def test_promo_create_rejects_bad_input():
    with pytest.raises(promo.PromoError):
        promo.create("a b", 10)
    with pytest.raises(promo.PromoError):
        promo.create("OKCODE", 0)
    promo.create("DUP", 5)
    with pytest.raises(promo.PromoError):
        promo.create("DUP", 5)


# ---- emails about the plan's life ------------------------------------------------------------
def _subjects(sent):
    return [m["Subject"] for m in sent]


def test_a_failed_renewal_is_announced_once(client, env):
    _, uid = _register(client)
    _stripe_sub(uid, status="past_due")
    assert lifecycle.send_billing_notices() == 1
    assert lifecycle.send_billing_notices() == 0                    # same period: no second mail
    assert any("payment" in s.lower() or "thanh toán" in s.lower() for s in _subjects(env))


def test_a_prepaid_plan_ending_soon_is_announced_unless_a_later_period_is_queued(client, env):
    _, uid = _register(client)
    _stripe_sub(uid, ref="o1", provider="payos", end=db.now() + 2 * 86400)
    _, uid2 = _register(client, "two@example.com")
    _stripe_sub(uid2, ref="o2", provider="payos", end=db.now() + 2 * 86400)
    _stripe_sub(uid2, ref="o3", provider="payos", end=db.now() + 32 * 86400)     # next period already paid
    assert lifecycle.send_billing_notices() == 1
    assert lifecycle.send_billing_notices() == 0


def test_a_lapsed_prepaid_plan_gets_one_ended_notice(client):
    _, uid = _register(client)
    _stripe_sub(uid, ref="o1", provider="payos", status="active", end=db.now() - 3600)
    assert lifecycle.send_billing_notices() == 1
    assert lifecycle.send_billing_notices() == 0


def test_no_notices_without_mail(client, monkeypatch):
    _, uid = _register(client)
    _stripe_sub(uid, status="past_due")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert lifecycle.send_billing_notices() == 0


def test_plan_catalogue_still_lists_every_cost(client):
    r = client.get("/api/billing/plans").json()
    assert set(r["costs"]) == set(plans.COSTS) and len(r["costs"]) >= 11
