"""The admin console's second half: charts, cross-user lists, CSV, manual plan, forced
verification, deleting an account, promo codes, and the AI-cost / margin figures."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio import admin, auth, credits, db, lifecycle_api, mailer, plans, promo
from studio.payments import service


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_DB_PATH", str(tmp_path / "studio.db"))
    monkeypatch.setenv("STUDIO_SECRET", "test-secret")
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("STUDIO_PAID", "1")
    monkeypatch.setenv("ADMIN_EMAILS", "boss@example.com")
    monkeypatch.setenv("FRONTEND_URL", "https://app.test")
    monkeypatch.setenv("VND_PER_USD", "25000")
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    sent = []
    monkeypatch.setattr(mailer, "_deliver", lambda msg: sent.append(msg))
    monkeypatch.setattr(mailer, "SYNC", True)
    db._initialised_for = None
    auth.clear_all_throttles()
    db.init()
    return sent


def _user(email="a@example.com", verified=True):
    u = auth.register(email, "correct horse", "Ann")
    if verified:
        with db.connection() as c:
            c.execute("UPDATE users SET email_verified_at = ? WHERE id = ?", (db.now(), u.id))
    return auth.get(u.id)


@pytest.fixture
def removed():
    return []


@pytest.fixture
def client(removed):
    app = FastAPI()
    app.include_router(lifecycle_api.build_router())
    app.include_router(admin.build_router(removed.append))
    return TestClient(app)


@pytest.fixture
def boss():
    return _user("boss@example.com")


def _h(user):
    return {"Authorization": f"Bearer {auth.issue_token(user)}"}


def _pay(uid, ref, amount, currency="usd", status="paid", kind="topup", item="topup_100", credits_=100):
    with db.write_connection() as c:
        service.record_payment(c, uid, "stripe" if currency == "usd" else "payos", ref, kind, item, amount,
                               currency, credits_, status, paid_at=db.now())


def test_new_routes_are_admin_only(client):
    normal = _user("n@example.com")
    for path in ("/series", "/payments", "/subscriptions", "/failed-projects", "/webhook-events",
                 "/invoice-requests", "/promos", "/export/users"):
        assert client.get("/api/admin" + path, headers=_h(normal)).status_code == 404, path
    assert client.delete("/api/admin/users/1", headers=_h(normal)).status_code == 404


def test_revenue_cost_and_margin(client, boss):
    u = _user()
    _pay(u.id, "pi_1", 1200, "usd")                                    # $12.00
    _pay(u.id, "o_1", 250_000, "vnd")                                  # 250,000 VND = $10.00
    credits.grant(u.id, "topup", 100, expires_at=None, source_ref="t")
    assert credits.spend_up_to(u.id, "job-1", "dubbing", 10)           # records an estimated cost
    ov = client.get("/api/admin/overview", headers=_h(boss)).json()
    eco = ov["economics_30d"]
    assert eco["revenue_usd"] == 22.0 and eco["ai_cost_usd"] > 0
    assert eco["margin_usd"] == round(22.0 - eco["ai_cost_usd"], 2)
    assert eco["by_plan"]["free"]["credits"] == 10
    detail = client.get(f"/api/admin/users/{u.id}", headers=_h(boss)).json()
    assert detail["revenue_usd"] == 22.0 and detail["ai_cost_usd"] == eco["ai_cost_usd"]


def test_series_fills_every_day(client, boss):
    u = _user()
    _pay(u.id, "pi_1", 500)
    days = client.get("/api/admin/series", params={"days": 7}, headers=_h(boss)).json()["days"]
    assert len(days) == 7 and days[-1]["revenue_usd"] == 5.0 and days[-1]["signups"] == 2
    assert all(d["revenue_usd"] == 0 for d in days[:-1])


def test_cross_user_lists_and_filters(client, boss):
    a, b = _user("a@example.com"), _user("b@example.com")
    _pay(a.id, "pi_a", 500)
    _pay(b.id, "pi_b", 900, status="refunded")
    h = _h(boss)
    allp = client.get("/api/admin/payments", headers=h).json()
    assert allp["total"] == 2 and {p["email"] for p in allp["payments"]} == {"a@example.com", "b@example.com"}
    assert client.get("/api/admin/payments", params={"status": "refunded"}, headers=h).json()["total"] == 1
    assert client.get("/api/admin/payments", params={"q": "a@exa"}, headers=h).json()["total"] == 1
    assert client.get("/api/admin/subscriptions", headers=h).json()["total"] == 0


def test_failed_projects_and_webhook_events(client, boss):
    u = _user()
    with db.write_connection() as c:
        c.execute("INSERT INTO projects (job_id, user_id, title, status, created_at, updated_at) "
                  "VALUES ('j1', ?, 'x', 'failed', ?, ?)", (u.id, db.now(), db.now()))
        c.execute("INSERT INTO projects (job_id, user_id, title, status, created_at, updated_at) "
                  "VALUES ('j2', ?, 'y', 'completed', ?, ?)", (u.id, db.now(), db.now()))
        service.claim_event(c, "stripe", "evt_1", "invoice.paid")
    h = _h(boss)
    assert [p["job_id"] for p in client.get("/api/admin/failed-projects", headers=h).json()["projects"]] == ["j1"]
    assert client.get("/api/admin/webhook-events", headers=h).json()["events"][0]["event_id"] == "evt_1"


def test_csv_export_defuses_formulas_and_is_audited(client, boss):
    evil = auth.register("e@example.com", "correct horse", "=HYPERLINK(\"http://x\")")
    h = _h(boss)
    r = client.get("/api/admin/export/users", headers=h)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "'=HYPERLINK" in r.text and ",=HYPERLINK" not in r.text
    assert client.get("/api/admin/export/secrets", headers=h).status_code == 400
    actions = [e["action"] for e in client.get("/api/admin/audit", headers=h).json()["entries"]]
    assert "export" in actions and evil.id


def test_set_plan_by_hand_expires_and_can_be_ended(client, boss):
    u = _user()
    h = _h(boss)
    r = client.post(f"/api/admin/users/{u.id}/plan", json={"plan": "pro", "days": 10, "note": "demo"}, headers=h)
    assert r.json() == {"plan": "pro"} and auth.get(u.id).plan == "pro"
    assert credits.balance(u.id)["plan_remaining"] == plans.PLANS["pro"].credits
    assert client.post(f"/api/admin/users/{u.id}/plan", json={"plan": "gold"}, headers=h).status_code == 422
    assert client.post(f"/api/admin/users/{u.id}/plan", json={"plan": "pro", "days": 0}, headers=h).status_code == 422
    # time passes: the period ends and the normal sweep returns the account to free
    with db.write_connection() as c:
        c.execute("UPDATE subscriptions SET current_period_end = ? WHERE user_id = ?", (db.now() - 99 * 86400, u.id))
    service.expire_due_subscriptions()
    assert auth.get(u.id).plan == "free"
    client.post(f"/api/admin/users/{u.id}/plan", json={"plan": "starter", "days": 5}, headers=h)
    assert client.post(f"/api/admin/users/{u.id}/plan", json={"plan": "free"}, headers=h).json() == {"plan": "free"}


def test_force_verify_and_resend_reset(client, boss, env):
    u = _user("new@example.com", verified=False)
    h = _h(boss)
    assert auth.get(u.id).email_verified is False
    assert client.post(f"/api/admin/users/{u.id}/verify-email", headers=h).status_code == 200
    assert auth.get(u.id).email_verified is True
    before = len(env)
    assert client.post(f"/api/admin/users/{u.id}/send-reset", headers=h).status_code == 200
    assert len(env) == before + 1 and env[-1]["To"] == "new@example.com"
    assert client.post("/api/admin/users/999/verify-email", headers=h).status_code == 404


def test_delete_user_keeps_payment_proof_and_files_are_removed(client, boss, removed):
    u = _user()
    _pay(u.id, "pi_keep", 500)
    with db.write_connection() as c:
        c.execute("INSERT INTO projects (job_id, user_id, title, status, created_at, updated_at) "
                  "VALUES ('jobX', ?, 'x', 'completed', ?, ?)", (u.id, db.now(), db.now()))
    h = _h(boss)
    assert client.delete(f"/api/admin/users/{u.id}", headers=h).json() == {"deleted": True}
    assert auth.get(u.id) is None and removed == ["jobX"]
    with db.connection() as c:
        assert c.execute("SELECT COUNT(*) FROM payment_records WHERE provider_ref = 'pi_keep'").fetchone()[0] == 1
    last = client.get("/api/admin/audit", headers=h).json()["entries"][0]
    assert last["action"] == "delete_user" and last["detail"]["email"] == "a@example.com"


def test_an_admin_cannot_delete_themselves_or_another_admin(client, boss, monkeypatch):
    other = _user("second@example.com")
    monkeypatch.setenv("ADMIN_EMAILS", "boss@example.com,second@example.com")
    h = _h(boss)
    assert client.delete(f"/api/admin/users/{boss.id}", headers=h).status_code == 400
    r = client.delete(f"/api/admin/users/{other.id}", headers=h)
    assert r.status_code == 403 and auth.get(other.id) is not None


def test_a_stripe_failure_aborts_the_deletion(client, boss, monkeypatch):
    from studio.payments import stripe_provider
    u = _user()
    with db.write_connection() as c:
        service.upsert_subscription(c, u.id, "stripe", "sub_1", "starter", "active", db.now(), db.now() + 86400)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")

    def boom(ref):
        raise stripe_provider.StripeError("down", 502)
    monkeypatch.setattr(stripe_provider, "cancel_subscription", boom)
    assert client.delete(f"/api/admin/users/{u.id}", headers=_h(boss)).status_code == 502
    assert auth.get(u.id) is not None


def test_promo_codes_from_the_console(client, boss):
    h = _h(boss)
    r = client.post("/api/admin/promos", json={"code": "LAUNCH", "credits": 30, "max_uses": 2}, headers=h)
    assert r.status_code == 200 and r.json()["credits"] == 30
    assert client.post("/api/admin/promos", json={"code": "LAUNCH", "credits": 30}, headers=h).status_code == 409
    assert client.post("/api/admin/promos", json={"code": "x y", "credits": 30}, headers=h).status_code == 422
    assert [c["code"] for c in client.get("/api/admin/promos", headers=h).json()["codes"]] == ["LAUNCH"]
    assert client.post("/api/admin/promos/LAUNCH/active", json={"active": False}, headers=h).status_code == 200
    u = _user()
    with pytest.raises(promo.PromoError):
        promo.redeem(u.id, "LAUNCH")
    assert client.post("/api/admin/promos/NOPE/active", json={"active": True}, headers=h).status_code == 404


def test_audit_log_filters_and_pages(client, boss):
    u = _user()
    h = _h(boss)
    client.post(f"/api/admin/users/{u.id}/grant", json={"credits": 5}, headers=h)
    client.post(f"/api/admin/users/{u.id}/disable", headers=h)
    only = client.get("/api/admin/audit", params={"action": "grant"}, headers=h).json()["entries"]
    assert [e["action"] for e in only] == ["grant"]
    page2 = client.get("/api/admin/audit", params={"limit": 1, "offset": 1}, headers=h).json()["entries"]
    assert len(page2) == 1 and page2[0]["action"] == "grant"
