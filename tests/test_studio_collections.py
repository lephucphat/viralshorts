import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio import api, auth, db, projects


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


def _project(user_id, job_id, title="clip"):
    projects.create(job_id, user_id, title, "url", "https://example.com/v")
    projects.finish(job_id, "completed", clip_count=2, top_score=80)


def test_favorite_flag_and_filter(client):
    h, uid = _signup(client, "a@example.com")
    _project(uid, "job-1")
    _project(uid, "job-2")
    assert client.put("/api/projects/job-1/favorite", json={"favorite": True}, headers=h).json()["favorite"] is True
    items = client.get("/api/projects?favorite=true", headers=h).json()["items"]
    assert [p["job_id"] for p in items] == ["job-1"]
    client.put("/api/projects/job-1/favorite", json={"favorite": False}, headers=h)
    assert client.get("/api/projects?favorite=true", headers=h).json()["total"] == 0


def test_collection_lifecycle(client):
    h, uid = _signup(client, "a@example.com")
    _project(uid, "job-1")
    _project(uid, "job-2")
    cid = client.post("/api/collections", json={"name": "  Podcast  clips "}, headers=h).json()["id"]
    assert client.post(f"/api/collections/{cid}/projects", json={"job_id": "job-1"}, headers=h).status_code == 200
    # adding twice is harmless
    assert client.post(f"/api/collections/{cid}/projects", json={"job_id": "job-1"}, headers=h).status_code == 200
    listed = client.get("/api/collections", headers=h).json()["items"]
    assert listed[0]["name"] == "Podcast clips" and listed[0]["count"] == 1
    inside = client.get(f"/api/projects?collection={cid}", headers=h).json()["items"]
    assert [p["job_id"] for p in inside] == ["job-1"]
    assert client.get("/api/projects/job-1/collections", headers=h).json()["ids"] == [cid]
    client.delete(f"/api/collections/{cid}/projects/job-1", headers=h)
    assert client.get(f"/api/projects?collection={cid}", headers=h).json()["total"] == 0
    # deleting the collection keeps the project
    client.post(f"/api/collections/{cid}/projects", json={"job_id": "job-2"}, headers=h)
    assert client.delete(f"/api/collections/{cid}", headers=h).status_code == 200
    assert client.get("/api/projects", headers=h).json()["total"] == 2


def test_name_rules(client):
    h, _ = _signup(client, "a@example.com")
    assert client.post("/api/collections", json={"name": "   "}, headers=h).status_code == 400
    assert client.post("/api/collections", json={"name": "Best"}, headers=h).status_code == 200
    dup = client.post("/api/collections", json={"name": "best"}, headers=h)
    assert dup.status_code == 409


def test_collections_are_private(client):
    ha, ua = _signup(client, "a@example.com")
    hb, ub = _signup(client, "b@example.com")
    _project(ua, "job-a")
    _project(ub, "job-b")
    cid = client.post("/api/collections", json={"name": "Mine"}, headers=ha).json()["id"]
    # B cannot see, fill, rename, delete or filter by A's collection
    assert client.get("/api/collections", headers=hb).json()["items"] == []
    assert client.post(f"/api/collections/{cid}/projects", json={"job_id": "job-b"}, headers=hb).status_code == 404
    assert client.patch(f"/api/collections/{cid}", json={"name": "x"}, headers=hb).status_code == 404
    assert client.delete(f"/api/collections/{cid}", headers=hb).status_code == 404
    assert client.get(f"/api/projects?collection={cid}", headers=hb).json()["total"] == 0
    # A cannot put B's project into their own collection
    assert client.post(f"/api/collections/{cid}/projects", json={"job_id": "job-b"}, headers=ha).status_code == 404
    # nor favourite it
    assert client.put("/api/projects/job-b/favorite", json={"favorite": True}, headers=ha).status_code == 404


def test_deleting_a_project_drops_only_the_link(client):
    h, uid = _signup(client, "a@example.com")
    _project(uid, "job-1")
    cid = client.post("/api/collections", json={"name": "Keep"}, headers=h).json()["id"]
    client.post(f"/api/collections/{cid}/projects", json={"job_id": "job-1"}, headers=h)
    assert client.delete("/api/projects/job-1", headers=h).status_code == 200
    assert client.get("/api/collections", headers=h).json()["items"][0]["count"] == 0
