import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio import api, auth, db, inbox


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_DB_PATH", str(tmp_path / "studio.db"))
    monkeypatch.setenv("STUDIO_SECRET", "test-secret-" + "x" * 40)
    monkeypatch.setenv("STUDIO_FREE_VERIFY", "0")
    db._initialised_for = None
    auth.clear_all_throttles()
    db.init()
    app = FastAPI()
    ctx = api.Context(job_status=lambda j: None, cancel_job=lambda j: False, remove_job_files=lambda j: None)
    app.include_router(api.build_router(ctx))
    return TestClient(app)


def _signup(client, email):
    r = client.post("/api/auth/register", json={"email": email, "password": "Correct-Horse-9!", "accept_terms": True})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user"]["id"]


def test_events_are_recorded_once_and_listed_newest_first(client):
    h, uid = _signup(client, "a@example.com")
    inbox.job_finished(uid, "job-1", "completed", "Podcast", 7)
    inbox.job_finished(uid, "job-1", "completed", "Podcast", 7)        # a retried hook: no duplicate
    inbox.job_finished(uid, "job-2", "failed", "Vlog")
    inbox.job_finished(uid, "job-3", "cancelled", "x")                  # cancelled is the user's own doing
    out = client.get("/api/inbox", headers=h).json()
    assert out["unread"] == 2
    assert [(i["kind"], i["ref"]) for i in out["items"]] == [("job_failed", "job-2"), ("clips_ready", "job-1")]
    assert out["items"][1]["data"] == {"title": "Podcast", "count": 7}


def test_mark_one_then_all_read(client):
    h, uid = _signup(client, "a@example.com")
    inbox.job_finished(uid, "job-1", "completed", "A", 1)
    inbox.job_finished(uid, "job-2", "completed", "B", 2)
    first = client.get("/api/inbox", headers=h).json()["items"][0]["id"]
    assert client.post("/api/inbox/read", headers=h, json={"id": first}).json()["changed"] == 1
    assert client.get("/api/inbox", headers=h).json()["unread"] == 1
    assert client.post("/api/inbox/read", headers=h, json={}).json()["changed"] == 1
    assert client.get("/api/inbox", headers=h).json()["unread"] == 0


def test_inbox_is_private(client):
    ha, ua = _signup(client, "a@example.com")
    hb, ub = _signup(client, "b@example.com")
    inbox.job_finished(ua, "job-a", "completed", "A", 3)
    assert client.get("/api/inbox", headers=hb).json() == {"items": [], "unread": 0}
    item = client.get("/api/inbox", headers=ha).json()["items"][0]["id"]
    assert client.post("/api/inbox/read", headers=hb, json={"id": item}).json()["changed"] == 0
    assert client.get("/api/inbox", headers=ha).json()["unread"] == 1


def test_unknown_kind_and_data_are_filtered(client):
    _, uid = _signup(client, "a@example.com")
    assert inbox.add(uid, "made_up", "x") is False
    inbox.add(uid, "clips_ready", "j", {"title": "  t  " * 100, "count": "5", "html": "<b>"})
    item = inbox.list_for_user(uid)["items"][0]
    assert set(item["data"]) == {"title", "count"} and len(item["data"]["title"]) <= 120 and item["data"]["count"] == 5


def test_only_the_newest_hundred_are_kept(client):
    _, uid = _signup(client, "a@example.com")
    for i in range(105):
        inbox.add(uid, "clips_ready", f"job-{i}", {"count": 1})
    items = inbox.list_for_user(uid, limit=100)["items"]
    assert len(items) == 100 and items[0]["ref"] == "job-104" and items[-1]["ref"] == "job-5"
