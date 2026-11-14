"""studio.api over HTTP: auth flow, library scoping, brand kit endpoints."""
import io

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from studio import api, auth, db, projects


class Ctx(api.Context):
    pass


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_DB_PATH", str(tmp_path / "studio.db"))
    monkeypatch.setenv("STUDIO_SECRET", "test-secret")
    monkeypatch.delenv("STUDIO_MONTHLY_MINUTES", raising=False)
    db._initialised_for = None
    auth.clear_all_throttles()
    live, removed, cancelled = {}, [], []

    ctx = api.Context(
        job_status=lambda job_id: live.get(job_id),
        cancel_job=lambda job_id: cancelled.append(job_id) or live.get(job_id) in ("queued", "processing"),
        remove_job_files=lambda job_id: removed.append(job_id),
    )
    app = FastAPI()
    app.include_router(api.build_router(ctx))
    return TestClient(app), live, removed, cancelled


def _register(client, email="a@example.com", password="correct horse"):
    r = client.post("/api/auth/register", json={"email": email, "password": password, "name": "Ann"})
    assert r.status_code == 200, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user"]


def _png():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGBA", (40, 20), (1, 2, 3, 255)).save(buf, format="PNG")
    return buf.getvalue()


def test_register_login_me(env):
    client, *_ = env
    headers, user = _register(client)
    assert user["email"] == "a@example.com" and "password_hash" not in str(user)
    me = client.get("/api/me", headers=headers).json()
    assert me["user"]["id"] == user["id"] and me["usage"]["limit"] == 300
    login = client.post("/api/auth/login", json={"email": "A@EXAMPLE.com", "password": "correct horse"})
    assert login.status_code == 200 and login.json()["token"]


def test_protected_routes_need_a_token(env):
    client, *_ = env
    for method, path in [("get", "/api/me"), ("get", "/api/projects"), ("get", "/api/brand-kits"),
                         ("get", "/api/usage"), ("post", "/api/jobs/x/cancel")]:
        r = getattr(client, method)(path)
        assert r.status_code == 401, (path, r.status_code)
    assert client.get("/api/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_error_shape_and_codes(env):
    client, *_ = env
    r = client.post("/api/auth/register", json={"email": "bad", "password": "correct horse"})
    assert r.status_code == 422 and r.json()["detail"]["error"] == "invalid_email"
    _register(client)
    dup = client.post("/api/auth/register", json={"email": "a@example.com", "password": "correct horse"})
    assert dup.status_code == 409 and dup.json()["detail"]["error"] == "email_taken"
    bad = client.post("/api/auth/login", json={"email": "a@example.com", "password": "wrong-wrong"})
    assert bad.status_code == 401 and bad.json()["detail"]["error"] == "bad_credentials"


def test_two_accounts_never_see_each_others_projects(env):
    client, live, removed, cancelled = env
    ha, ua = _register(client, "a@example.com")
    hb, ub = _register(client, "b@example.com")
    projects.create("job-a", ua["id"], "Alpha", "file")
    projects.create("job-b", ub["id"], "Beta", "file")

    assert [p["job_id"] for p in client.get("/api/projects", headers=ha).json()["items"]] == ["job-a"]
    assert client.get("/api/projects/job-b", headers=ha).status_code == 404
    assert client.patch("/api/projects/job-b", headers=ha, json={"title": "x"}).status_code == 404
    assert client.delete("/api/projects/job-b", headers=ha).status_code == 404
    assert client.post("/api/jobs/job-b/cancel", headers=ha).status_code == 404
    # nothing was touched on the other account's job
    assert "job-b" not in removed and "job-b" not in cancelled
    assert projects.get_by_job("job-b")["title"] == "Beta"


def test_rename_and_delete_remove_files(env):
    client, live, removed, cancelled = env
    h, u = _register(client)
    projects.create("job-1", u["id"], "Old", "file")
    assert client.patch("/api/projects/job-1", headers=h, json={"title": "New"}).json()["title"] == "New"
    assert client.delete("/api/projects/job-1", headers=h).json() == {"deleted": True}
    assert removed == ["job-1"] and cancelled == ["job-1"]
    assert client.get("/api/projects/job-1", headers=h).status_code == 404


def test_cancel_marks_cancelled_only_when_something_was_stopped(env):
    client, live, removed, cancelled = env
    h, u = _register(client)
    projects.create("running", u["id"], "R", "file")
    projects.create("done", u["id"], "D", "file")
    live["running"] = "processing"
    live["done"] = "completed"
    assert client.post("/api/jobs/running/cancel", headers=h).json() == {"cancelled": True}
    assert projects.get_by_job("running")["status"] == "cancelled"
    assert client.post("/api/jobs/done/cancel", headers=h).json() == {"cancelled": False}
    assert projects.get_by_job("done")["status"] == "queued"


def test_list_reconciles_with_the_live_job_table(env):
    client, live, *_ = env
    h, u = _register(client)
    projects.create("finished", u["id"], "F", "file")
    projects.create("lost", u["id"], "L", "file")
    live["finished"] = "completed"
    # a row nobody has worked on for a while and no live job: interrupted
    with db.connection() as c:
        c.execute("UPDATE projects SET updated_at = updated_at - 1000 WHERE job_id = 'lost'")
    items = {p["job_id"]: p["status"] for p in client.get("/api/projects", headers=h).json()["items"]}
    assert items == {"finished": "completed", "lost": "failed"}


def test_account_deletion_removes_job_files(env):
    client, live, removed, cancelled = env
    h, u = _register(client)
    projects.create("job-1", u["id"], "T", "file")
    projects.create("job-2", u["id"], "T2", "file")
    wrong = client.request("DELETE", "/api/me", headers=h, json={"password": "nope nope nope"})
    assert wrong.status_code == 401 and removed == []
    ok = client.request("DELETE", "/api/me", headers=h, json={"password": "correct horse"})
    assert ok.status_code == 200 and sorted(removed) == ["job-1", "job-2"]
    assert client.get("/api/me", headers=h).status_code == 401   # token now points at nobody


def test_password_change_returns_fresh_token_and_kills_old(env):
    client, *_ = env
    h, _u = _register(client)
    r = client.post("/api/me/password", headers=h, json={"current": "correct horse", "new": "another pass 123"})
    assert r.status_code == 200
    assert client.get("/api/me", headers=h).status_code == 401
    fresh = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/api/me", headers=fresh).status_code == 200


def test_brand_kit_flow_and_signed_logo_url(env):
    client, *_ = env
    h, _u = _register(client)
    created = client.post("/api/brand-kits", headers=h, json={"name": "Acme", "primary_color": "#ff0000"})
    assert created.status_code == 200
    kit = created.json()
    assert kit["is_default"] and kit["logo_url"] is None and kit["primary_color"] == "#FF0000"

    bad = client.post("/api/brand-kits", headers=h, json={"name": "Bad", "layout": "nope"})
    assert bad.status_code == 422

    up = client.post(f"/api/brand-kits/{kit['id']}/logo", headers=h,
                     files={"file": ("logo.png", _png(), "image/png")})
    assert up.status_code == 200 and up.json()["logo_url"]
    logo_url = up.json()["logo_url"]
    # an <img> has no headers: the signed URL alone must work, a tampered one must not
    assert client.get(logo_url).status_code == 200
    assert client.get(logo_url.replace("sig=", "sig=0")).status_code == 404
    assert client.get(f"/api/brand-kits/{kit['id']}/logo").status_code == 404

    junk = client.post(f"/api/brand-kits/{kit['id']}/logo", headers=h,
                       files={"file": ("x.png", b"<html></html>", "image/png")})
    assert junk.status_code == 422 and junk.json()["detail"]["error"] == "invalid_logo"

    patched = client.patch(f"/api/brand-kits/{kit['id']}", headers=h, json={"logo_scale": 0.2}).json()
    assert patched["logo_scale"] == 0.2
    assert client.delete(f"/api/brand-kits/{kit['id']}/logo", headers=h).json()["has_logo"] is False
    assert client.delete(f"/api/brand-kits/{kit['id']}", headers=h).json() == {"deleted": True}


def test_brand_kits_are_private(env):
    client, *_ = env
    ha, _ = _register(client, "a@example.com")
    hb, _ = _register(client, "b@example.com")
    kit = client.post("/api/brand-kits", headers=ha, json={"name": "Mine"}).json()
    assert client.get("/api/brand-kits", headers=hb).json()["items"] == []
    assert client.patch(f"/api/brand-kits/{kit['id']}", headers=hb, json={"name": "x"}).status_code == 404
    assert client.delete(f"/api/brand-kits/{kit['id']}", headers=hb).status_code == 404
    assert client.post(f"/api/brand-kits/{kit['id']}/logo", headers=hb,
                       files={"file": ("l.png", _png(), "image/png")}).status_code == 404
