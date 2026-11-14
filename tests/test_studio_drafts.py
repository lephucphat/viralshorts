"""Tool drafts: unfinished work is kept per person, listed, reopened and deleted over the API."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio import api, auth, db, drafts


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
    return {"Authorization": f"Bearer {r.json()['token']}"}


DATA = {"step": 2, "mode": "manual", "manualTitle": "My title", "selectedTitle": "My title",
        "generatedThumbnails": [{"url": "/thumbnails/s1/thumb_a_1.jpg", "text": "WOW"}],
        "evil": "dropped"}


def test_save_list_get_delete(client):
    h = _signup(client, "a@example.com")
    assert client.put("/api/drafts/abcdefgh12", headers=h, json={"kind": "thumbnails", "data": DATA}).status_code == 200
    items = client.get("/api/drafts?kind=thumbnails", headers=h).json()["items"]
    assert [(i["id"], i["title"], i["step"], i["preview"]) for i in items] == [
        ("abcdefgh12", "My title", 2, "/thumbnails/s1/thumb_a_1.jpg")]
    got = client.get("/api/drafts/abcdefgh12", headers=h).json()
    assert got["data"]["manualTitle"] == "My title" and "evil" not in got["data"]
    assert client.delete("/api/drafts/abcdefgh12", headers=h).status_code == 200
    assert client.get("/api/drafts", headers=h).json()["items"] == []
    assert client.get("/api/drafts/abcdefgh12", headers=h).status_code == 404


def test_saving_again_updates_the_same_draft(client):
    h = _signup(client, "a@example.com")
    client.put("/api/drafts/abcdefgh12", headers=h, json={"data": DATA})
    client.put("/api/drafts/abcdefgh12", headers=h, json={"data": {**DATA, "step": 3}})
    items = client.get("/api/drafts", headers=h).json()["items"]
    assert len(items) == 1 and items[0]["step"] == 3


def test_drafts_are_private(client):
    a, b = _signup(client, "a@example.com"), _signup(client, "b@example.com")
    client.put("/api/drafts/abcdefgh12", headers=a, json={"data": DATA})
    assert client.get("/api/drafts", headers=b).json()["items"] == []
    assert client.get("/api/drafts/abcdefgh12", headers=b).status_code == 404
    assert client.delete("/api/drafts/abcdefgh12", headers=b).status_code == 404
    # the same client-made id under another account is its own draft
    assert client.put("/api/drafts/abcdefgh12", headers=b, json={"data": {**DATA, "manualTitle": "B"}}).status_code == 200
    assert client.get("/api/drafts/abcdefgh12", headers=a).json()["data"]["manualTitle"] == "My title"


def test_requires_login(client):
    assert client.get("/api/drafts").status_code == 401
    assert client.put("/api/drafts/abcdefgh12", json={"data": DATA}).status_code == 401


@pytest.mark.parametrize("draft_id,body,code", [
    ("short", {"data": DATA}, 400),                              # id too short
    ("abcdefgh12", {"kind": "nope", "data": DATA}, 400),         # unknown kind
    ("abcdefgh12", {"data": {"step": 0}}, 400),                  # nothing worth keeping
    ("abcdefgh12", {"data": {"step": 1, "description": "x" * 300_000}}, 422),   # too big
])
def test_bad_saves_are_refused(client, draft_id, body, code):
    h = _signup(client, "a@example.com")
    assert client.put(f"/api/drafts/{draft_id}", headers=h, json=body).status_code == code


def test_preview_never_points_outside_thumbnails():
    assert drafts._preview({"selectedThumbnail": "http://evil/x.jpg",
                            "generatedThumbnails": [{"url": "/thumbnails/../../.env"}]}) == ""


def test_oldest_drafts_are_dropped(client, monkeypatch):
    monkeypatch.setattr(drafts, "KEEP_PER_USER", 2)
    h = _signup(client, "a@example.com")
    for i in range(3):
        client.put(f"/api/drafts/draft{i}xxxxx", headers=h, json={"data": {**DATA, "manualTitle": f"t{i}"}})
    assert {i["id"] for i in client.get("/api/drafts", headers=h).json()["items"]} == {"draft1xxxxx", "draft2xxxxx"}
