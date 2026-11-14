import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio import api, auth, db


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


def test_create_list_delete(client):
    h = _signup(client, "a@example.com")
    r = client.post("/api/recipes", headers=h, json={
        "name": "  Podcast   dài ", "settings": {"genre": "podcast", "clipLength": "long", "captions": False}})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    assert r.json()["name"] == "Podcast dài"
    listed = client.get("/api/recipes", headers=h).json()["items"]
    assert listed[0]["settings"] == {"genre": "podcast", "clipLength": "long", "captions": False}
    assert client.delete(f"/api/recipes/{rid}", headers=h).status_code == 200
    assert client.get("/api/recipes", headers=h).json()["items"] == []


def test_unknown_and_wrongly_typed_settings_are_dropped(client):
    h = _signup(client, "a@example.com")
    r = client.post("/api/recipes", headers=h, json={"name": "x", "settings": {
        "genre": "vlog", "evil": "<script>", "captions": "yes", "autoHook": True, "keywords": "a" * 500}})
    s = r.json()["settings"]
    assert "evil" not in s and "captions" not in s
    assert s["genre"] == "vlog" and s["autoHook"] is True and len(s["keywords"]) == 200


def test_name_rules_and_limit(client):
    h = _signup(client, "a@example.com")
    assert client.post("/api/recipes", headers=h, json={"name": "  ", "settings": {}}).status_code == 400
    assert client.post("/api/recipes", headers=h, json={"name": "Best", "settings": {}}).status_code == 200
    assert client.post("/api/recipes", headers=h, json={"name": "best", "settings": {}}).status_code == 409
    for i in range(19):
        assert client.post("/api/recipes", headers=h, json={"name": f"r{i}", "settings": {}}).status_code == 200
    assert client.post("/api/recipes", headers=h, json={"name": "over", "settings": {}}).status_code == 400


def test_recipes_are_private(client):
    ha = _signup(client, "a@example.com")
    hb = _signup(client, "b@example.com")
    rid = client.post("/api/recipes", headers=ha, json={"name": "Mine", "settings": {}}).json()["id"]
    assert client.get("/api/recipes", headers=hb).json()["items"] == []
    assert client.delete(f"/api/recipes/{rid}", headers=hb).status_code == 404
    assert client.get("/api/recipes", headers=ha).json()["items"][0]["name"] == "Mine"
