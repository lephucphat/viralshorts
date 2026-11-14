"""app.py with ACCOUNTS_ENABLED=1: login required, per-user isolation, library sync.

The app module reads its flags at import time, so it is imported fresh, inside a
throwaway working directory, with the flag set; the previously imported module
(if any) is put back afterwards so no other test sees this configuration.
"""
import asyncio
import os
import subprocess
import sys

import pytest
from starlette.testclient import TestClient

_ENV = {
    "ACCOUNTS_ENABLED": "1",
    "STUDIO_SECRET": "integration-secret",
    "STUDIO_MONTHLY_MINUTES": "300",
    "GEMINI_API_KEY": "test-key",
    "QUALITY_GATE_MIN_HEIGHT": "0",
    "MIN_SOURCE_SECONDS": "0",
    "LLM_BASE_URL": "",
    "LLM_API_KEY": "",
    "LLM_MODEL": "",
}


@pytest.fixture(scope="module")
def appmod(tmp_path_factory):
    work = tmp_path_factory.mktemp("studio_app")
    saved_env = {k: os.environ.get(k) for k in [*_ENV, "STUDIO_DB_PATH", "BILLING_ENABLED"]}
    saved_cwd = os.getcwd()
    saved_mod = sys.modules.pop("app", None)
    os.environ.update(_ENV)
    os.environ["STUDIO_DB_PATH"] = str(work / "studio.db")
    os.environ.pop("BILLING_ENABLED", None)
    os.chdir(work)
    try:
        import importlib
        module = importlib.import_module("app")
        assert module.ACCOUNTS_ENABLED and module._multi_tenant() and not module.BILLING_ENABLED
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
    with db.connection() as conn:   # every test starts from an empty library
        conn.execute("DELETE FROM users")   # cascades to projects, kits, usage
    return TestClient(appmod.app)


def _signup(client, email):
    r = client.post("/api/auth/register", json={"email": email, "password": "correct horse"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user"]["id"]


def _start(client, headers, name="talk.mp4"):
    return client.post("/api/process", headers=headers,
                       data={"acknowledged": "true"},
                       files={"file": (name, b"not really a video", "video/mp4")})


def test_config_advertises_accounts(client):
    cfg = client.get("/api/config").json()
    assert cfg["accountsEnabled"] is True and cfg["billingEnabled"] is False


def test_anonymous_cannot_start_work_or_upload(client):
    assert _start(client, {}).status_code == 401
    assert client.post("/api/uploads", json={"filename": "a.mp4"}).status_code == 401
    assert client.post("/api/thumbnail/upload",
                       files={"file": ("a.mp4", b"x", "video/mp4")}).status_code in (401, 402)


def test_a_started_job_lands_in_the_library_and_is_private(client, appmod):
    ha, _ = _signup(client, "a@example.com")
    hb, _ = _signup(client, "b@example.com")
    started = _start(client, ha)
    assert started.status_code == 200, started.text
    job_id = started.json()["job_id"]

    items = client.get("/api/projects", headers=ha).json()["items"]
    assert [p["job_id"] for p in items] == [job_id]
    assert items[0]["title"] == "talk" and items[0]["status"] == "queued"
    assert client.get("/api/projects", headers=hb).json()["items"] == []

    # the job itself: owner sees it, a stranger gets a 404 (not a 403)
    assert client.get(f"/api/status/{job_id}", headers=ha).status_code == 200
    assert client.get(f"/api/status/{job_id}", headers=hb).status_code == 404
    assert client.get(f"/api/status/{job_id}").status_code == 404
    assert client.get(f"/api/source-url/{job_id}", headers=hb).status_code == 404
    assert client.get(f"/api/source-url/{job_id}", headers=ha).status_code == 200
    assert client.get(f"/api/jobs/{job_id}/download-all", headers=hb).status_code in (404, 409)


def test_source_is_only_reachable_with_a_valid_signature_or_ownership(client, appmod):
    ha, _ = _signup(client, "a@example.com")
    hb, _ = _signup(client, "b@example.com")
    job_id = _start(client, ha).json()["job_id"]
    signed = client.get(f"/api/source-url/{job_id}", headers=ha).json()["url"]
    assert "sig=" in signed
    assert client.get(signed).status_code == 200                       # capability URL
    assert client.get(signed.replace("sig=", "sig=0")).status_code == 404
    assert client.get(f"/api/source/{job_id}", headers=hb).status_code == 404
    assert client.get(f"/api/source/{job_id}").status_code == 404


def test_cancel_and_delete_are_owner_only_and_clean_up(client, appmod):
    ha, _ = _signup(client, "a@example.com")
    hb, _ = _signup(client, "b@example.com")
    job_id = _start(client, ha).json()["job_id"]
    assert client.post(f"/api/jobs/{job_id}/cancel", headers=hb).status_code == 404
    assert client.delete(f"/api/projects/{job_id}", headers=hb).status_code == 404
    assert appmod.jobs[job_id]["status"] == "queued"

    assert client.post(f"/api/jobs/{job_id}/cancel", headers=ha).json() == {"cancelled": True}
    assert appmod.jobs[job_id]["status"] == "cancelled"
    assert client.get(f"/api/projects/{job_id}", headers=ha).json()["status"] == "cancelled"

    upload_files = [f for f in os.listdir(appmod.UPLOAD_DIR) if f.startswith(job_id)]
    assert upload_files, "the uploaded source should exist before delete"
    assert client.delete(f"/api/projects/{job_id}", headers=ha).json() == {"deleted": True}
    assert job_id not in appmod.jobs
    assert not os.path.exists(os.path.join(appmod.OUTPUT_DIR, job_id))
    assert not [f for f in os.listdir(appmod.UPLOAD_DIR) if f.startswith(job_id)]
    assert client.get("/api/projects", headers=ha).json()["items"] == []


def test_a_cancelled_queued_job_is_skipped_by_the_worker(client, appmod):
    ha, _ = _signup(client, "a@example.com")
    job_id = _start(client, ha).json()["job_id"]
    client.post(f"/api/jobs/{job_id}/cancel", headers=ha)
    asyncio.run(appmod.run_job(job_id, appmod.jobs[job_id]))   # would spawn main.py if it ran
    assert appmod.jobs[job_id]["status"] == "cancelled"
    assert "_process" not in appmod.jobs[job_id]


def test_concurrent_job_cap(client, appmod):
    ha, _ = _signup(client, "a@example.com")
    for _ in range(appmod.STUDIO_MAX_ACTIVE_JOBS):
        assert _start(client, ha).status_code == 200
    third = _start(client, ha)
    assert third.status_code == 429 and third.json()["detail"]["error"] == "too_many_jobs"
    # someone else is not affected by A's queue
    hb, _ = _signup(client, "b@example.com")
    assert _start(client, hb).status_code == 200


def test_monthly_allowance_blocks_new_jobs(client, appmod, monkeypatch):
    from studio import usage
    monkeypatch.setenv("STUDIO_MONTHLY_MINUTES", "2")
    ha, uid = _signup(client, "a@example.com")
    usage.charge(uid, "earlier", 2)
    r = _start(client, ha)
    assert r.status_code == 402
    assert r.json()["detail"]["error"] == "quota_exceeded" and r.json()["detail"]["minutes_remaining"] == 0


def test_finished_job_updates_library_cover_and_usage(client, appmod, tmp_path):
    from studio import projects, usage
    ha, uid = _signup(client, "a@example.com")
    job_id = _start(client, ha).json()["job_id"]
    out = os.path.join(appmod.OUTPUT_DIR, job_id)
    os.makedirs(out, exist_ok=True)
    clip = os.path.join(out, "clip_1.mp4")
    made = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                           "color=c=blue:s=216x384:d=2", "-pix_fmt", "yuv420p", clip],
                          capture_output=True)
    if made.returncode != 0:
        pytest.skip("ffmpeg cannot synthesise a test clip here")
    job = appmod.jobs[job_id]
    job["status"] = "completed"
    job["output_dir"] = out
    job["result"] = {"clips": [
        {"video_url": f"/videos/{job_id}/clip_1.mp4", "viral_score": 82, "predicted_score": 70},
        {"video_url": f"/videos/{job_id}/clip_2.mp4", "predicted_score": 55},
    ]}
    asyncio.run(appmod._studio_job_finished(job_id))
    project = projects.get_by_job(job_id)
    assert project["status"] == "completed"
    assert project["clip_count"] == 2 and project["top_score"] == 82
    assert project["cover_url"] == f"/videos/{job_id}/cover.jpg"
    assert os.path.exists(os.path.join(out, "cover.jpg"))
    assert project["minutes_charged"] >= 1 and usage.used_minutes(uid) == project["minutes_charged"]
    # finishing twice must not charge twice
    asyncio.run(appmod._studio_job_finished(job_id))
    assert usage.used_minutes(uid) == project["minutes_charged"]


def test_failed_job_costs_nothing(client, appmod):
    from studio import projects, usage
    ha, uid = _signup(client, "a@example.com")
    job_id = _start(client, ha).json()["job_id"]
    appmod.jobs[job_id]["status"] = "failed"
    asyncio.run(appmod._studio_job_finished(job_id))
    assert projects.get_by_job(job_id)["status"] == "failed"
    assert usage.used_minutes(uid) == 0


def test_account_deletion_wipes_that_users_job_files(client, appmod):
    ha, _ = _signup(client, "a@example.com")
    hb, _ = _signup(client, "b@example.com")
    ja = _start(client, ha).json()["job_id"]
    jb = _start(client, hb).json()["job_id"]
    r = client.request("DELETE", "/api/me", headers=ha, json={"password": "correct horse"})
    assert r.status_code == 200
    assert ja not in appmod.jobs and jb in appmod.jobs
    assert client.get(f"/api/status/{jb}", headers=hb).status_code == 200


def test_remove_job_files_refuses_non_job_paths(appmod, tmp_path):
    outside = tmp_path / "precious"
    outside.mkdir()
    (outside / "keep.txt").write_text("x")
    appmod._studio_remove_job_files("../" + os.path.relpath(str(outside), appmod.OUTPUT_DIR))
    appmod._studio_remove_job_files("..")
    assert (outside / "keep.txt").exists()


def _kit(client, headers, **fields):
    r = client.post("/api/brand-kits", headers=headers, json={"name": "Mine", **fields})
    assert r.status_code in (200, 201), r.text
    return r.json()


def test_creation_controls_reach_the_job_environment(client, appmod):
    ha, _ = _signup(client, "a@example.com")
    r = client.post("/api/process", headers=ha, data={
        "acknowledged": "true", "genre": "podcast", "keywords": "vốn, khởi nghiệp",
        "clip_length": "long", "time_start": "0:10", "time_end": "2:00",
        "source_language": "vi"},
        files={"file": ("talk.mp4", b"not really a video", "video/mp4")})
    assert r.status_code == 200, r.text
    env = appmod.jobs[r.json()["job_id"]]["env"]
    assert env["CLIP_GENRE"] == "podcast" and env["CLIP_KEYWORDS"] == "vốn, khởi nghiệp"
    assert (env["CLIP_MIN_SECONDS"], env["CLIP_MAX_SECONDS"]) == ("60.0", "90.0")
    assert (env["SOURCE_START"], env["SOURCE_END"]) == ("10", "120")
    assert env["WHISPER_LANGUAGE"] == "vi"
    project = client.get(f"/api/projects/{r.json()['job_id']}", headers=ha).json()
    assert project["options"]["genre"] == "podcast" and project["options"]["clip_length"] == "long"


@pytest.mark.parametrize("field,value", [("genre", "nope"), ("clip_length", "epic"),
                                         ("time_start", "xx"), ("source_language", "english"),
                                         ("brand_kit_id", "abc")])
def test_bad_controls_are_a_400_and_start_nothing(client, appmod, field, value):
    ha, _ = _signup(client, "a@example.com")
    r = client.post("/api/process", headers=ha, data={"acknowledged": "true", field: value},
                    files={"file": ("talk.mp4", b"x", "video/mp4")})
    assert r.status_code == 400, r.text
    assert client.get("/api/projects", headers=ha).json()["items"] == []


def test_brand_kit_defaults_apply_and_belong_to_the_owner(client, appmod):
    ha, _ = _signup(client, "a@example.com")
    hb, _ = _signup(client, "b@example.com")
    kit = _kit(client, ha, caption_preset="beast", layout="screencast",
               output_format="square", hook_style="yellow")
    r = client.post("/api/process", headers=ha, data={
        "acknowledged": "true", "brand_kit_id": str(kit["id"]), "auto_hook": "true"},
        files={"file": ("a.mp4", b"x", "video/mp4")})
    assert r.status_code == 200, r.text
    job = appmod.jobs[r.json()["job_id"]]
    assert job["env"]["CAPTION_PRESET"] == "beast"
    assert job["env"]["AUTO_HOOK_STYLE"] == "yellow"
    assert job["cmd"][job["cmd"].index("--format") + 1] == "square"
    assert "SPLIT_LAYOUT" not in job["env"]

    # somebody else's kit is a 404, not a silent fallback
    other = client.post("/api/process", headers=hb, data={
        "acknowledged": "true", "brand_kit_id": str(kit["id"])},
        files={"file": ("b.mp4", b"x", "video/mp4")})
    assert other.status_code == 404


def test_request_fields_beat_the_kit(client, appmod):
    ha, _ = _signup(client, "a@example.com")
    kit = _kit(client, ha, output_format="square", is_default=True)
    r = client.post("/api/process", headers=ha, data={
        "acknowledged": "true", "output_format": "horizontal"},
        files={"file": ("a.mp4", b"x", "video/mp4")})
    job = appmod.jobs[r.json()["job_id"]]
    assert job["cmd"][job["cmd"].index("--format") + 1] == "horizontal"


def test_none_opts_out_of_the_default_kit(client, appmod):
    ha, _ = _signup(client, "a@example.com")
    _kit(client, ha, caption_preset="beast", is_default=True)
    r = client.post("/api/process", headers=ha, data={"acknowledged": "true", "brand_kit_id": "none"},
                    files={"file": ("a.mp4", b"x", "video/mp4")})
    assert "CAPTION_PRESET" not in appmod.jobs[r.json()["job_id"]]["env"]
    r = client.post("/api/process", headers=ha, data={"acknowledged": "true"},
                    files={"file": ("b.mp4", b"x", "video/mp4")})
    assert appmod.jobs[r.json()["job_id"]]["env"]["CAPTION_PRESET"] == "beast"


def test_tool_keys_come_from_the_server_environment(appmod, monkeypatch):
    monkeypatch.setenv("FAL_KEY", "fal-from-env")
    assert appmod._tool_key(None, "FAL_KEY") == "fal-from-env"
    assert appmod._tool_key(appmod.SERVER_KEY, "FAL_KEY") == "fal-from-env"
    assert appmod._tool_key("their-own", "FAL_KEY") == "their-own"
    monkeypatch.delenv("FAL_KEY")
    assert appmod._tool_key(None, "FAL_KEY") is None


def test_upload_post_never_falls_back_to_the_operators_key(client, appmod, monkeypatch):
    monkeypatch.setenv("UPLOAD_POST_API_KEY", "operator-key")
    ha, _ = _signup(client, "a@example.com")

    class Req:
        headers = {}
    key, profile = asyncio.run(appmod.resolve_upload_post(Req()))
    assert key is None and profile is None
    Req.headers = {"X-Upload-Post-Key": "mine"}
    assert asyncio.run(appmod.resolve_upload_post(Req()))[0] == "mine"


def test_missing_ai_key_is_a_server_problem_not_the_callers(client, appmod, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(appmod.llm_backend, "active", lambda: False)
    ha, _ = _signup(client, "a@example.com")
    r = _start(client, ha)
    assert r.status_code == 503 and "administrator" in r.json()["detail"]
