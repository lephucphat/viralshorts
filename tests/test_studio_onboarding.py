"""studio: first-run checklist, welcome email, yearly prices in the plan catalogue.

No SMTP server and no network: ``mailer._deliver`` is replaced by a list. Each test has its
own database.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio import api, auth, brand_kits, db, lifecycle, mailer, onboarding, plans
from studio.payments import api as payments_api


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_DB_PATH", str(tmp_path / "studio.db"))
    monkeypatch.setenv("STUDIO_SECRET", "test-secret")
    monkeypatch.setenv("FRONTEND_URL", "https://app.test")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("REQUIRE_VERIFIED_EMAIL", raising=False)
    monkeypatch.delenv("STUDIO_PRICES_FINAL", raising=False)
    monkeypatch.delenv("STUDIO_YEARLY_BILLING", raising=False)
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


def _register(client, email="a@example.com", lang="vi"):
    r = client.post("/api/auth/register", json={"email": email, "password": "correct horse",
                                                "name": "Ann", "lang": lang})
    assert r.status_code == 200, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user"]["id"]


def _steps(client, h):
    r = client.get("/api/me/onboarding", headers=h)
    assert r.status_code == 200, r.text
    return {s["id"]: s["done"] for s in r.json()["steps"]}, r.json()


# ---- checklist -----------------------------------------------------------------------------------
def test_new_account_starts_with_nothing_done_and_no_verify_step_without_mail(client):
    h, _ = _register(client)
    steps, body = _steps(client, h)
    assert steps == {"brand_kit": False, "first_clip": False, "social": False, "pricing": False}
    assert body["done"] == 0 and body["total"] == 4 and not body["complete"] and not body["dismissed"]


def test_brand_kit_and_project_steps_are_derived_from_real_rows(client):
    h, uid = _register(client)
    brand_kits.create(uid, {"name": "Mine"})
    with db.write_connection() as c:
        c.execute("INSERT INTO projects (job_id, user_id, status, created_at, updated_at) VALUES ('j1',?,?,?,?)",
                  (uid, "failed", db.now(), db.now()))
    steps, _ = _steps(client, h)
    assert steps["brand_kit"] is True
    assert steps["first_clip"] is False            # a failed project is not a first clip
    with db.write_connection() as c:
        c.execute("INSERT INTO projects (job_id, user_id, status, created_at, updated_at) VALUES ('j2',?,?,?,?)",
                  (uid, "completed", db.now(), db.now()))
    assert _steps(client, h)[0]["first_clip"] is True


def test_client_can_only_report_pricing_and_social(client):
    h, _ = _register(client)
    assert client.post("/api/me/onboarding/pricing", headers=h).json()["done"] == 1
    assert client.post("/api/me/onboarding/social", headers=h).json()["done"] == 2
    # idempotent
    assert client.post("/api/me/onboarding/social", headers=h).json()["done"] == 2
    for derived in ("brand_kit", "first_clip", "verify_email", "nonsense"):
        assert client.post(f"/api/me/onboarding/{derived}", headers=h).status_code == 422


def test_dismiss_is_remembered_and_checklist_requires_a_session(client):
    h, _ = _register(client)
    assert client.post("/api/me/onboarding/dismiss", headers=h).json()["dismissed"] is True
    assert _steps(client, h)[1]["dismissed"] is True
    assert client.get("/api/me/onboarding").status_code == 401


def test_each_account_has_its_own_state(client):
    a, _ = _register(client, "a@example.com")
    b, _ = _register(client, "b@example.com")
    client.post("/api/me/onboarding/pricing", headers=a)
    assert _steps(client, a)[0]["pricing"] is True
    assert _steps(client, b)[0]["pricing"] is False


def test_verify_step_appears_only_when_verification_is_enforced(client, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    h, uid = _register(client)
    steps, _ = _steps(client, h)
    assert steps["verify_email"] is False and list(steps)[0] == "verify_email"
    with db.write_connection() as c:
        c.execute("UPDATE users SET email_verified_at = ? WHERE id = ?", (db.now(), uid))
    assert _steps(client, h)[0]["verify_email"] is True


def test_erasing_the_account_removes_the_onboarding_row(client):
    h, uid = _register(client)
    client.post("/api/me/onboarding/pricing", headers=h)
    auth.delete_account(uid, "correct horse")
    with db.connection() as c:
        assert c.execute("SELECT COUNT(*) FROM onboarding WHERE user_id = ?", (uid,)).fetchone()[0] == 0


# ---- welcome email ----------------------------------------------------------------------------------
def test_welcome_goes_out_once_at_signup_when_verification_is_not_required(client, env, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("REQUIRE_VERIFIED_EMAIL", "0")
    _, uid = _register(client, lang="en")
    welcome = [m for m in env if "Welcome" in m["Subject"]]
    assert len(welcome) == 1 and welcome[0]["To"] == "a@example.com"
    assert "https://app.test/#/projects" in welcome[0].get_body(preferencelist=("plain",)).get_content()
    assert lifecycle.send_welcome(uid) is False        # idempotent
    assert len([m for m in env if "Welcome" in m["Subject"]]) == 1


def test_welcome_waits_for_the_verified_inbox_when_verification_is_required(client, env, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    _, uid = _register(client)
    assert not [m for m in env if "Chào mừng" in m["Subject"]]     # only the verification mail so far
    token = lifecycle.create_token(uid, "verify", 3600)
    lifecycle.verify_email(token)
    welcome = [m for m in env if "Chào mừng" in m["Subject"]]
    assert len(welcome) == 1                                        # vi account gets the vi mail


def test_no_welcome_without_mail(client, env):
    _register(client)
    assert env == []


# ---- plan catalogue ---------------------------------------------------------------------------------------
def test_catalogue_carries_yearly_prices_the_business_contact_plan_and_placeholder_flags(client):
    r = client.get("/api/billing/plans").json()
    starter = next(p for p in r["plans"] if p["id"] == "starter")
    months = 12 - starter["yearly_discount_months"]
    assert starter["price_usd_cents_yearly"] == starter["price_usd_cents"] * months
    assert starter["price_vnd_yearly"] == starter["price_vnd"] * months
    free = next(p for p in r["plans"] if p["id"] == "free")
    assert free["price_usd_cents_yearly"] == 0
    assert [p["id"] for p in r["contact_plans"]] == ["business"] and r["contact_plans"][0]["contact"] is True
    assert "business" not in plans.PLANS                  # nobody can check out or be granted it
    assert r["prices_placeholder"] is True and r["yearly_checkout"] is False


def test_flags_flip_with_the_environment(client, monkeypatch):
    monkeypatch.setenv("STUDIO_PRICES_FINAL", "1")
    monkeypatch.setenv("STUDIO_YEARLY_BILLING", "1")
    r = client.get("/api/billing/plans").json()
    assert r["prices_placeholder"] is False and r["yearly_checkout"] is True
