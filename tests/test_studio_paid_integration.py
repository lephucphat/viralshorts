"""app.py with ACCOUNTS_ENABLED=1 and STUDIO_PAID=1: credits are reserved, settled and refunded.

Same technique as test_studio_integration.py: the app module reads its flags at
import time, so it is imported fresh in a throwaway directory.
"""
import asyncio
import os
import sys

import pytest
from starlette.testclient import TestClient

_ENV = {
    "ACCOUNTS_ENABLED": "1",
    "STUDIO_PAID": "1",
    "STUDIO_SECRET": "paid-secret",
    "GEMINI_API_KEY": "test-key",
    "FAL_KEY": "test-fal",
    "ELEVENLABS_API_KEY": "test-eleven",
    "QUALITY_GATE_MIN_HEIGHT": "0",
    "MIN_SOURCE_SECONDS": "0",
    "LLM_BASE_URL": "",
    "LLM_API_KEY": "",
    "LLM_MODEL": "",
}


@pytest.fixture(scope="module")
def appmod(tmp_path_factory):
    work = tmp_path_factory.mktemp("studio_paid_app")
    saved_env = {k: os.environ.get(k) for k in [*_ENV, "STUDIO_DB_PATH", "BILLING_ENABLED",
                                                "DAILY_AI_BUDGET_CREDITS"]}
    saved_cwd = os.getcwd()
    saved_mod = sys.modules.pop("app", None)
    os.environ.update(_ENV)
    os.environ["STUDIO_DB_PATH"] = str(work / "studio.db")
    os.environ.pop("BILLING_ENABLED", None)
    os.environ.pop("DAILY_AI_BUDGET_CREDITS", None)
    os.chdir(work)
    try:
        import importlib
        module = importlib.import_module("app")
        assert module.ACCOUNTS_ENABLED and module._paid()
        yield module
    finally:
        os.chdir(saved_cwd)
        sys.modules.pop("app", None)
        if saved_mod is not None:
            sys.modules["app"] = saved_mod
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@pytest.fixture
def client(appmod):
    from studio import auth, db
    auth.clear_all_throttles()
    appmod.jobs.clear()
    with db.connection() as conn:
        conn.execute("DELETE FROM users")      # cascades to grants, ledger, projects
    return TestClient(appmod.app)


def _signup(client, email="a@example.com"):
    r = client.post("/api/auth/register", json={"email": email, "password": "correct horse"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user"]["id"]


def _start(client, headers):
    return client.post("/api/process", headers=headers, data={"acknowledged": "true"},
                       files={"file": ("talk.mp4", b"not really a video", "video/mp4")})


def _set_plan(uid, plan):
    from studio import db
    with db.connection() as conn:
        conn.execute("UPDATE users SET plan = ? WHERE id = ?", (plan, uid))


def _balance(uid):
    from studio import credits
    return credits.balance(uid)["remaining"]


def test_usage_endpoint_reports_credits_and_plan(client):
    h, uid = _signup(client)
    body = client.get("/api/usage", headers=h).json()
    assert body["paid"] is True and body["plan"] == "free"
    assert body["remaining"] == body["credits"]["remaining"] > 0
    assert "clips" in body["features"] and "ai_shorts" not in body["features"]


def test_starting_a_job_reserves_credits(client, appmod):
    h, uid = _signup(client)
    before = _balance(uid)
    r = _start(client, h)
    assert r.status_code == 200, r.text
    assert _balance(uid) == before - 1                       # one minute minimum
    assert appmod.jobs[r.json()["job_id"]]["reservation_id"]


def test_out_of_credits_is_a_402_with_numbers(client, appmod):
    from studio import credits
    h, uid = _signup(client)
    credits.spend_up_to(uid, "drain", "process", _balance(uid))
    r = _start(client, h)
    assert r.status_code == 402
    d = r.json()["detail"]
    assert d["error"] == "quota_exceeded" and d["credits_remaining"] == 0 and d["credits_required"] >= 1


def test_free_plan_runs_one_job_at_a_time_and_paid_plans_more(client):
    h, uid = _signup(client)
    assert _start(client, h).status_code == 200
    second = _start(client, h)
    assert second.status_code == 429 and second.json()["detail"]["error"] == "too_many_jobs"
    _set_plan(uid, "pro")
    from studio import credits, db
    credits.grant(uid, "plan", 100, expires_at=db.now() + 3600, source_ref="t-pro")
    assert _start(client, h).status_code == 200


def test_failed_job_is_refunded(client, appmod):
    h, uid = _signup(client)
    before = _balance(uid)
    job_id = _start(client, h).json()["job_id"]
    assert _balance(uid) == before - 1
    appmod.jobs[job_id]["status"] = "failed"
    asyncio.run(appmod._studio_job_finished(job_id))
    assert _balance(uid) == before


def test_cancelling_a_queued_job_refunds_immediately(client, appmod):
    h, uid = _signup(client)
    before = _balance(uid)
    job_id = _start(client, h).json()["job_id"]
    assert client.post(f"/api/jobs/{job_id}/cancel", headers=h).json() == {"cancelled": True}
    assert _balance(uid) == before


def test_completed_job_keeps_its_charge_and_settles_once(client, appmod, tmp_path):
    h, uid = _signup(client)
    before = _balance(uid)
    job_id = _start(client, h).json()["job_id"]
    out = os.path.join(appmod.OUTPUT_DIR, job_id)
    os.makedirs(out, exist_ok=True)
    job = appmod.jobs[job_id]
    job["status"] = "completed"
    job["output_dir"] = out
    job["result"] = {"clips": [{"video_url": f"/videos/{job_id}/clip_1.mp4", "viral_score": 80}]}
    asyncio.run(appmod._studio_job_finished(job_id))
    assert _balance(uid) == before - 1
    asyncio.run(appmod._studio_job_finished(job_id))          # finishing twice must not charge twice
    assert _balance(uid) == before - 1


def test_expensive_features_are_gated_by_plan(client):
    h, _ = _signup(client)                                      # free plan
    gen = client.post("/api/saasshorts/generate", headers=h, json={
        "script": {"title": "t", "segments": []}, "actor_description": "a woman"})
    assert gen.status_code == 402 and gen.json()["detail"]["error"] == "plan_required"
    assert gen.json()["detail"]["feature"] == "ai_shorts"
    actors = client.post("/api/saasshorts/actor-options", headers=h,
                         json={"actor_description": "a woman"})
    assert actors.status_code == 402 and actors.json()["detail"]["error"] == "plan_required"


def test_a_client_supplied_key_cannot_dodge_the_meter(client, appmod):
    import asyncio as aio
    from starlette.requests import Request

    scope = {"type": "http", "headers": [(b"x-gemini-key", b"attacker-key")], "method": "GET",
             "path": "/", "query_string": b""}
    key = aio.run(appmod.resolve_gemini(Request(scope)))
    assert key == "test-key"                                    # the operator's key, not the header's
    assert appmod._tool_key("attacker-key", "FAL_KEY") == "test-fal"


# ---- billing endpoints ----------------------------------------------------------------------
def _stripe_post(client, payload: dict, secret="whsec_it"):
    import hashlib
    import hmac
    import json
    import time
    raw = json.dumps(payload).encode()
    t = int(time.time())
    sig = hmac.new(secret.encode(), f"{t}.".encode() + raw, hashlib.sha256).hexdigest()
    return client.post("/api/stripe/webhook", content=raw,
                       headers={"stripe-signature": f"t={t},v1={sig}", "content-type": "application/json"})


def test_plans_are_public_and_list_the_enabled_providers(client, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("PAYOS_CLIENT_ID", raising=False)
    body = client.get("/api/billing/plans").json()
    assert {p["id"] for p in body["plans"]} == {"free", "starter", "pro"}
    assert body["providers"] == [] and "ai_short_premium" in body["costs"]


def test_checkout_needs_login_and_a_configured_provider(client, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("PAYOS_CLIENT_ID", raising=False)
    assert client.post("/api/billing/checkout", json={"kind": "topup", "item": "topup_100"}).status_code == 401
    h, _ = _signup(client)
    r = client.post("/api/billing/checkout", headers=h, json={"kind": "topup", "item": "topup_100"})
    assert r.status_code == 503 and r.json()["detail"]["error"] == "payments_off"


def test_stripe_webhook_rejects_forgeries_and_applies_real_events(client, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_it")
    h, uid = _signup(client)
    event = {"id": "evt_it_1", "type": "checkout.session.completed", "data": {"object": {
        "id": "cs_it", "mode": "payment", "payment_status": "paid", "amount_total": 500, "currency": "usd",
        "metadata": {"user_id": str(uid), "kind": "topup", "item": "topup_100"}}}}
    before = _balance(uid)

    forged = client.post("/api/stripe/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=00"})
    assert forged.status_code == 400
    assert _balance(uid) == before

    ok = _stripe_post(client, event)
    assert ok.status_code == 200 and ok.json()["result"] == "applied"
    assert _balance(uid) == before + 100
    assert _stripe_post(client, event).json()["result"] == "duplicate"      # Stripe retries are harmless
    assert _balance(uid) == before + 100

    status = client.get("/api/billing/status", headers=h).json()
    assert status["plan"]["id"] == "free" and status["payments"][0]["credits"] == 100


def test_stripe_webhook_asks_for_a_retry_when_the_account_is_not_linked_yet(client, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_it")
    r = _stripe_post(client, {"id": "evt_early", "type": "invoice.paid", "data": {"object": {
        "id": "in_x", "subscription": "sub_unknown", "customer": "cus_unknown", "amount_paid": 100,
        "currency": "usd", "lines": {"data": [{"period": {"start": 1, "end": 2}}]}}}})
    assert r.status_code == 503 and r.json()["detail"]["error"] == "retry_later"


def test_payos_webhook_rejects_a_bad_signature(client, monkeypatch):
    monkeypatch.setenv("PAYOS_CHECKSUM_KEY", "k")
    r = client.post("/api/payos/webhook", json={"success": True, "signature": "00",
                                                "data": {"orderCode": 1, "amount": 1}})
    assert r.status_code == 400


# ---- clip library: archive on finish, restore on open -----------------------------------------
JOB_A = "aaaaaaaa-1111-2222-3333-444444444444"


def _fake_store(monkeypatch):
    import test_studio_archive as t
    from studio import archive
    fake = t.FakeS3()
    monkeypatch.setenv("ARCHIVE_BUCKET", "clips")
    monkeypatch.setenv("ARCHIVE_ACCESS_KEY_ID", "k")
    monkeypatch.setenv("ARCHIVE_SECRET_ACCESS_KEY", "s")
    monkeypatch.setattr(archive, "_client_factory", lambda: fake)
    return fake


def _finished_job(appmod, uid, plan):
    import json
    from studio import projects
    _set_plan(uid, plan)
    d = os.path.join(appmod.OUTPUT_DIR, JOB_A)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "talk_clip_1.mp4"), "wb") as f:
        f.write(b"CLIP" * 64)
    with open(os.path.join(d, "talk_metadata.json"), "w") as f:
        json.dump({"shorts": [{"video_url": f"/videos/{JOB_A}/talk_clip_1.mp4"}]}, f)
    projects.create(JOB_A, uid, "talk", "file")
    return d


def test_paid_plan_clips_are_archived_then_restored_for_the_owner_only(client, appmod, monkeypatch):
    import shutil
    import threading
    fake = _fake_store(monkeypatch)
    h, uid = _signup(client)
    d = _finished_job(appmod, uid, "starter")
    appmod._studio_archive_in_background(JOB_A, uid, d)
    for t in threading.enumerate():
        if t is not threading.current_thread() and t.daemon:
            t.join(timeout=10)
    assert any(k.endswith("talk_clip_1.mp4") for (_, k) in fake.objects)
    assert client.get("/api/projects", headers=h).json()["items"][0]["archive"]["state"] == "available"

    shutil.rmtree(d)                      # the working folder is swept
    appmod.jobs.pop(JOB_A, None)

    h2, _ = _signup(client, "other@example.com")
    assert client.get(f"/api/status/{JOB_A}", headers=h2).status_code in (403, 404)
    assert not os.path.exists(d)          # a stranger does not trigger a restore

    r = client.get(f"/api/status/{JOB_A}", headers=h)
    assert r.status_code == 200, r.text
    assert os.path.exists(os.path.join(d, "talk_clip_1.mp4"))
    assert open(os.path.join(d, ".owner")).read() == str(uid)


def test_free_plan_clips_are_not_archived(client, appmod, monkeypatch):
    fake = _fake_store(monkeypatch)
    h, uid = _signup(client)
    d = _finished_job(appmod, uid, "free")
    appmod._studio_archive_in_background(JOB_A, uid, d)
    assert fake.objects == {}
