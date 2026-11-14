"""The posting calendar (studio/schedule.py + /api/calendar): ownership, validation, status flow."""
import json
import time

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from studio import account, api, auth, db, projects, schedule


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_DB_PATH", str(tmp_path / "studio.db"))
    monkeypatch.setenv("STUDIO_SECRET", "test-secret")
    monkeypatch.delenv("SUPPORT_EMAIL", raising=False)
    db._initialised_for = None
    auth.clear_all_throttles()
    ctx = api.Context(job_status=lambda j: None, cancel_job=lambda j: False, remove_job_files=lambda j: None)
    app = FastAPI()
    app.include_router(api.build_router(ctx))
    return TestClient(app)


def _user(client, email):
    r = client.post("/api/auth/register", json={"email": email, "password": "correct horse", "name": "T"})
    assert r.status_code == 200, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user"]["id"]


def _soon(hours=48):
    return time.time() + hours * 3600


def _make(client, headers, job="job-1", **over):
    body = {"job_id": job, "clip_index": 2, "title": "Clip hay", "description": "mô tả",
            "platforms": ["tiktok", "youtube"], "scheduled_for": _soon(), "timezone": "Asia/Ho_Chi_Minh"}
    body.update(over)
    return client.post("/api/calendar", json=body, headers=headers)


def test_requires_sign_in(env):
    for method, path in [("get", "/api/calendar?start=1&end=2"), ("post", "/api/calendar"),
                         ("delete", "/api/calendar/1"), ("post", "/api/calendar/1/status")]:
        assert getattr(env, method)(path).status_code in (401, 422), path
    assert env.get("/api/calendar?start=1&end=2").status_code == 401


def test_create_list_and_range(env):
    h, uid = _user(env, "a@example.com")
    projects.create("job-1", uid, "Podcast", "file")
    r = _make(env, h)
    assert r.status_code == 200, r.text
    post = r.json()
    assert post["status"] == "planned" and post["platforms"] == ["tiktok", "youtube"]
    assert post["timezone"] == "Asia/Ho_Chi_Minh" and post["clip_index"] == 2

    now = time.time()
    got = env.get(f"/api/calendar?start={now}&end={now + 7 * 86400}", headers=h).json()["items"]
    assert [p["id"] for p in got] == [post["id"]]
    # a window that does not contain it
    far = env.get(f"/api/calendar?start={now + 10 * 86400}&end={now + 20 * 86400}", headers=h).json()["items"]
    assert far == []
    # a window wider than ~2 months or backwards is refused
    assert env.get(f"/api/calendar?start={now}&end={now + 90 * 86400}", headers=h).status_code == 422
    assert env.get(f"/api/calendar?start={now}&end={now - 5}", headers=h).status_code == 422


def test_cannot_plan_someone_elses_project_or_see_their_posts(env):
    ha, a = _user(env, "a@example.com")
    hb, b = _user(env, "b@example.com")
    projects.create("job-a", a, "Mine", "file")
    stranger = _make(env, hb, job="job-a")
    assert stranger.status_code == 404 and stranger.json()["detail"]["error"] == "not_found"
    post = _make(env, ha, job="job-a").json()
    now = time.time()
    assert env.get(f"/api/calendar?start={now}&end={now + 5 * 86400}", headers=hb).json()["items"] == []
    for call in (lambda: env.patch(f"/api/calendar/{post['id']}", json={"title": "x"}, headers=hb),
                 lambda: env.delete(f"/api/calendar/{post['id']}", headers=hb),
                 lambda: env.post(f"/api/calendar/{post['id']}/status", json={"status": "cancelled"}, headers=hb)):
        assert call().status_code == 404
    assert schedule.get(a, post["id"])["title"] == "Clip hay"


@pytest.mark.parametrize("over,code", [
    ({"platforms": []}, "bad_platforms"),
    ({"platforms": ["myspace"]}, "bad_platforms"),
    ({"scheduled_for": time.time() - 5 * 86400}, "past_date"),
    ({"scheduled_for": time.time() + 400 * 86400}, "too_far"),
    ({"timezone": "Not A Zone!"}, "bad_timezone"),
    ({"clip_index": -1}, "bad_clip"),
])
def test_validation(env, over, code):
    h, uid = _user(env, "a@example.com")
    projects.create("job-1", uid, "P", "file")
    r = _make(env, h, **over)
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["error"] == code


def test_edit_only_before_it_is_handed_to_the_queue(env):
    h, uid = _user(env, "a@example.com")
    projects.create("job-1", uid, "P", "file")
    pid = _make(env, h).json()["id"]
    moved = _soon(100)
    r = env.patch(f"/api/calendar/{pid}", json={"scheduled_for": moved, "title": "Mới"}, headers=h).json()
    assert r["scheduled_for"] == moved and r["title"] == "Mới"
    sent = env.post(f"/api/calendar/{pid}/status", json={"status": "scheduled", "vendor_job_id": "up-1"}, headers=h)
    assert sent.status_code == 200 and sent.json()["vendor_job_id"] == "up-1"
    locked = env.patch(f"/api/calendar/{pid}", json={"title": "x"}, headers=h)
    assert locked.status_code == 409 and locked.json()["detail"]["error"] == "locked"
    # a post still queued at Upload-Post cannot be deleted from here: it would be published anyway
    gone = env.delete(f"/api/calendar/{pid}", headers=h)
    assert gone.status_code == 409 and gone.json()["detail"]["error"] == "cancel_first"
    assert env.post(f"/api/calendar/{pid}/status", json={"status": "cancelled"}, headers=h).json()["status"] == "cancelled"
    assert env.delete(f"/api/calendar/{pid}", headers=h).json() == {"deleted": True}


def test_status_flow_refuses_impossible_moves(env):
    h, uid = _user(env, "a@example.com")
    projects.create("job-1", uid, "P", "file")
    pid = _make(env, h).json()["id"]
    bad = env.post(f"/api/calendar/{pid}/status", json={"status": "published"}, headers=h)
    assert bad.status_code == 409 and bad.json()["detail"]["error"] == "bad_transition"
    assert env.post(f"/api/calendar/{pid}/status", json={"status": "nonsense"}, headers=h).status_code == 422
    failed = env.post(f"/api/calendar/{pid}/status", json={"status": "failed", "error": "x" * 500}, headers=h).json()
    assert failed["status"] == "failed" and len(failed["error"]) == 300
    # editing a failed post makes it ready to send again and clears the error
    again = env.patch(f"/api/calendar/{pid}", json={"title": "Thử lại"}, headers=h).json()
    assert again["status"] == "planned" and again["error"] == ""
    env.post(f"/api/calendar/{pid}/status", json={"status": "scheduled", "vendor_job_id": "u"}, headers=h)
    done = env.post(f"/api/calendar/{pid}/status", json={"status": "published"}, headers=h).json()
    assert done["status"] == "published"
    # published is final
    assert env.post(f"/api/calendar/{pid}/status", json={"status": "planned"}, headers=h).status_code == 409


def test_limit_per_user(env, monkeypatch):
    h, uid = _user(env, "a@example.com")
    projects.create("job-1", uid, "P", "file")
    monkeypatch.setattr(schedule, "MAX_PER_USER", 2)
    assert _make(env, h).status_code == 200 and _make(env, h).status_code == 200
    third = _make(env, h)
    assert third.status_code == 409 and third.json()["detail"]["error"] == "too_many"


def test_posts_leave_with_the_account_and_appear_in_the_export(env):
    h, uid = _user(env, "a@example.com")
    projects.create("job-1", uid, "P", "file")
    _make(env, h)
    exported = account.export_data(uid)
    assert exported["scheduled_posts"][0]["job_id"] == "job-1"
    json.dumps(exported)                                             # serialisable
    auth.erase_account(uid)
    with db.connection() as c:
        assert c.execute("SELECT COUNT(*) AS n FROM scheduled_posts").fetchone()["n"] == 0


def test_help_contact_uses_support_email(env, monkeypatch):
    assert env.get("/api/help/contact").json() == {"email": ""}
    monkeypatch.setenv("SUPPORT_EMAIL", " help@viralshorts.test ")
    assert env.get("/api/help/contact").json() == {"email": "help@viralshorts.test"}
