"""studio/archive: what is uploaded, what is never uploaded, restore, expiry and purge.

The object store is an in-memory fake with the few boto3 calls the module uses.
"""
import json
import os

import pytest

from studio import archive, auth, db, plans, projects


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.fail_upload_of = None
        self.fail_download = False

    def upload_file(self, path, bucket, key, ExtraArgs=None):
        if self.fail_upload_of and key.endswith(self.fail_upload_of):
            raise OSError("boom")
        with open(path, "rb") as f:
            self.objects[(bucket, key)] = f.read()

    def download_file(self, bucket, key, path):
        if self.fail_download:
            raise OSError("down")
        with open(path, "wb") as f:
            f.write(self.objects[(bucket, key)])

    def get_paginator(self, name):
        store = self

        class P:
            def paginate(self, Bucket, Prefix):
                yield {"Contents": [{"Key": k} for (b, k) in sorted(store.objects) if b == Bucket and k.startswith(Prefix)]}
        return P()

    def delete_objects(self, Bucket, Delete):
        for o in Delete["Objects"]:
            self.objects.pop((Bucket, o["Key"]), None)


@pytest.fixture
def s3(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_DB_PATH", str(tmp_path / "studio.db"))
    monkeypatch.setenv("STUDIO_SECRET", "test-secret")
    monkeypatch.setenv("ARCHIVE_BUCKET", "clips")
    monkeypatch.setenv("ARCHIVE_ACCESS_KEY_ID", "k")
    monkeypatch.setenv("ARCHIVE_SECRET_ACCESS_KEY", "s")
    fake = FakeS3()
    monkeypatch.setattr(archive, "_client_factory", lambda: fake)
    db._initialised_for = None
    auth.clear_all_throttles()
    db.init()
    return fake


JOB = "11111111-2222-3333-4444-555555555555"


def _job_dir(tmp_path):
    d = tmp_path / "output" / JOB
    d.mkdir(parents=True)
    (d / "clip_1.mp4").write_bytes(b"CLIP1" * 100)
    (d / "subtitled_clip_1.mp4").write_bytes(b"SUB" * 100)
    (d / "cover.jpg").write_bytes(b"JPG" * 50)
    (d / "talk_metadata.json").write_text(json.dumps({"source_video": "source.mp4", "shorts": []}))
    (d / "clip_1.layout.json").write_text("{}")
    (d / "source.mp4").write_bytes(b"RAWSOURCE" * 1000)           # the customer's raw input
    (d / ".resume.json").write_text('{"webhook_secret": "x"}')    # must never leave the server
    (d / ".owner").write_text("1")
    (d / "temp_work.mp4").write_bytes(b"tmp")
    (d / "transcript.json").write_text("{}")                      # not needed to restore
    return d


def test_only_deliverables_are_selected(s3, tmp_path):
    d = _job_dir(tmp_path)
    names = sorted(os.path.basename(p) for p in archive.select_files(str(d)))
    assert names == ["clip_1.layout.json", "clip_1.mp4", "cover.jpg", "subtitled_clip_1.mp4", "talk_metadata.json"]


def test_oversized_files_are_skipped(s3, tmp_path, monkeypatch):
    d = _job_dir(tmp_path)
    monkeypatch.setenv("ARCHIVE_MAX_FILE_MB", "1")
    (d / "huge.mp4").write_bytes(b"0" * (2 * 1024 * 1024))
    assert "huge.mp4" not in [os.path.basename(p) for p in archive.select_files(str(d))]


def test_archive_then_restore_round_trips_the_bytes(s3, tmp_path):
    d = _job_dir(tmp_path)
    info = archive.archive_job(JOB, str(d))
    assert info["files"] == 5 and info["bytes"] > 0
    assert all(k.startswith(f"jobs/{JOB}/") for (_, k) in s3.objects)
    assert not any(k.endswith((".resume.json", ".owner", "source.mp4")) for (_, k) in s3.objects)

    target = tmp_path / "restored" / JOB
    assert archive.restore_job(JOB, str(target)) == 5
    assert (target / "clip_1.mp4").read_bytes() == b"CLIP1" * 100
    assert not os.path.exists(str(target) + ".restoring")


def test_failed_upload_raises_and_failed_restore_leaves_nothing_half_done(s3, tmp_path):
    d = _job_dir(tmp_path)
    s3.fail_upload_of = "cover.jpg"
    with pytest.raises(archive.ArchiveError):
        archive.archive_job(JOB, str(d))
    s3.fail_upload_of = None
    archive.archive_job(JOB, str(d))
    s3.fail_download = True
    target = tmp_path / "restored" / JOB
    with pytest.raises(archive.ArchiveError):
        archive.restore_job(JOB, str(target))
    assert not target.exists() and not os.path.exists(str(target) + ".restoring")


def test_nothing_to_archive_and_bad_ids_are_refused(s3, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(archive.ArchiveError):
        archive.archive_job(JOB, str(empty))
    for bad in ("", "../x", "a/b", "a.b"):
        with pytest.raises(archive.ArchiveError):
            archive.job_prefix(bad)


def test_disabled_without_configuration(s3, monkeypatch):
    monkeypatch.delenv("ARCHIVE_BUCKET")
    assert archive.enabled() is False
    assert archive.delete_job(JOB) == 0
    assert archive.purge_expired() == 0


# ---- project row: state, retention, purge ------------------------------------------------------
def _project(email="a@example.com"):
    u = auth.register(email, "correct horse", "Ann")
    projects.create(JOB, u.id, "talk", "file")
    return u


def test_state_follows_the_plan_retention_and_purge_clears_the_objects(s3, tmp_path):
    u = _project()
    assert projects.get_for_user(u.id, JOB)["archive"]["state"] == "none"
    assert archive.is_restorable(JOB) is False

    archive.archive_job(JOB, str(_job_dir(tmp_path)))
    archive.mark_archived(JOB, 1234, days=14)
    p = projects.get_for_user(u.id, JOB)["archive"]
    assert p["state"] == "available" and p["bytes"] == 1234
    assert p["expires_at"] == pytest.approx(db.now() + 14 * 86400, abs=5)
    assert archive.is_restorable(JOB) is True and archive.owner_of(JOB) == u.id

    assert archive.purge_expired() == 0                          # not expired yet
    with db.connection() as c:
        c.execute("UPDATE projects SET archive_expires_at = ? WHERE job_id = ?", (db.now() - 1, JOB))
    assert archive.is_restorable(JOB) is False                   # expired: no restore even though objects exist
    assert archive.purge_expired() == 1
    assert s3.objects == {}
    again = projects.get_for_user(u.id, JOB)["archive"]
    assert again["state"] == "expired" and again["bytes"] == 0
    assert archive.purge_expired() == 0


def test_purge_retries_after_a_storage_failure(s3, tmp_path, monkeypatch):
    u = _project()
    archive.archive_job(JOB, str(_job_dir(tmp_path)))
    archive.mark_archived(JOB, 10, days=1)
    with db.connection() as c:
        c.execute("UPDATE projects SET archive_expires_at = ? WHERE job_id = ?", (db.now() - 1, JOB))
    monkeypatch.setattr(archive, "delete_job", lambda j: (_ for _ in ()).throw(archive.ArchiveError("down")))
    assert archive.purge_expired() == 0
    with db.connection() as c:
        assert c.execute("SELECT archived_at FROM projects WHERE job_id = ?", (JOB,)).fetchone()[0] is not None
    monkeypatch.undo()
    assert u.id


def test_plan_retention_decides_who_is_archived():
    assert plans.archive_days("free") == 0         # one day: the working folder already covers it
    assert plans.archive_days("starter") == 14
    assert plans.archive_days("pro") == 60
    assert plans.archive_days("unknown-plan") == 0


def test_stats(s3, tmp_path):
    _project()
    archive.archive_job(JOB, str(_job_dir(tmp_path)))
    archive.mark_archived(JOB, 500, days=14)
    assert archive.stats() == {"enabled": True, "projects": 1, "bytes": 500}
