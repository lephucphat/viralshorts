"""The durable clip library: finished projects copied to S3-compatible object storage.

Why it exists: the server's ``output/`` folder is a working directory, swept after a day and
wiped by a redeploy, but a paying customer's plan promises their clips for 14 or 60 days. The
files go to a bucket (Cloudflare R2, AWS S3, MinIO, anything speaking the S3 API) and come back
on demand when the project is reopened.

Written for this project: it does **not** use ``cloud/`` (Commercial licence) and not
``s3_uploader.py`` either, whose gallery lists a whole shared bucket, which in a many-user
product would show one customer's clips to another.

Layout: ``jobs/<job_id>/<file>``. A job id is an unguessable uuid and ownership is decided by the
``projects`` table, never by the key, so the keys carry no user data.

What goes up: deliverables (the clip and its derivatives, cover, captions) and the small JSON
files a restore needs (``*_metadata.json``, ``*.layout.json``). Never dotfiles (the resume manifest
holds a webhook secret) and never the uploaded source video.

Configuration (all required to switch it on): ``ARCHIVE_BUCKET``, ``ARCHIVE_ACCESS_KEY_ID``,
``ARCHIVE_SECRET_ACCESS_KEY``; for R2/MinIO also ``ARCHIVE_ENDPOINT_URL``; ``ARCHIVE_REGION``
(default ``auto``).
"""

import logging
import os
import posixpath
import shutil
from typing import Callable, Iterable, List, Optional

from . import db

log = logging.getLogger("studio.archive")

PREFIX = "jobs"
DELIVERABLE_EXTENSIONS = frozenset({
    ".mp4", ".webm", ".mov", ".m4v", ".mp3", ".m4a", ".wav",
    ".jpg", ".jpeg", ".png", ".webp", ".srt", ".vtt", ".ass", ".zip",
})
RESTORE_JSON_SUFFIXES = ("_metadata.json", ".layout.json")


class ArchiveError(Exception):
    """Storage is configured but a call to it failed."""


# ---- configuration ----------------------------------------------------------------------------
def enabled() -> bool:
    return bool(os.environ.get("ARCHIVE_BUCKET", "").strip()
                and os.environ.get("ARCHIVE_ACCESS_KEY_ID", "").strip()
                and os.environ.get("ARCHIVE_SECRET_ACCESS_KEY", "").strip())


def bucket() -> str:
    return os.environ.get("ARCHIVE_BUCKET", "").strip()


def max_file_bytes() -> int:
    try:
        return max(1, int(os.environ.get("ARCHIVE_MAX_FILE_MB", "500"))) * 1024 * 1024
    except ValueError:
        return 500 * 1024 * 1024


_client_factory: Optional[Callable[[], object]] = None   # tests inject a fake here


def _client():
    if _client_factory is not None:
        return _client_factory()
    import boto3
    from botocore.config import Config
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("ARCHIVE_ENDPOINT_URL", "").strip() or None,
        aws_access_key_id=os.environ["ARCHIVE_ACCESS_KEY_ID"].strip(),
        aws_secret_access_key=os.environ["ARCHIVE_SECRET_ACCESS_KEY"].strip(),
        region_name=os.environ.get("ARCHIVE_REGION", "auto").strip() or "auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 4, "mode": "standard"}))


# ---- keys and selection -----------------------------------------------------------------------
def job_prefix(job_id: str) -> str:
    _check_job_id(job_id)
    return f"{PREFIX}/{job_id}/"


def _check_job_id(job_id: str) -> None:
    # The id ends up in an object key and, on restore, a directory name.
    if not job_id or any(c in job_id for c in "/\\.") or len(job_id) > 80:
        raise ArchiveError("bad job id")


def should_archive(filename: str) -> bool:
    name = os.path.basename(filename)
    if not name or name.startswith(".") or name.startswith("temp_"):
        return False
    if name.endswith(RESTORE_JSON_SUFFIXES):
        return True
    return posixpath.splitext(name)[1].lower() in DELIVERABLE_EXTENSIONS


def _content_type(name: str) -> str:
    import mimetypes
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def select_files(directory: str) -> List[str]:
    """The files of a job directory that belong in the archive, within the size cap."""
    cap = max_file_bytes()
    skip = _source_names(directory)
    out = []
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if (os.path.isfile(path) and name not in skip and should_archive(name)
                and 0 < os.path.getsize(path) <= cap):
            out.append(path)
    return out


def _source_names(directory: str) -> set:
    """A URL job keeps the downloaded source video in its own folder, named in the metadata.
    It is the customer's raw input, often gigabytes: not part of the library."""
    import glob
    import json
    names = set()
    for meta in glob.glob(os.path.join(glob.escape(directory), "*_metadata.json")):
        try:
            with open(meta, "r", encoding="utf-8") as f:
                src = json.load(f).get("source_video")
        except (OSError, ValueError):
            continue
        if src:
            names.add(os.path.basename(str(src)))
    return names


# ---- upload / download / delete ----------------------------------------------------------------
def upload_file(job_id: str, path: str) -> int:
    """Upload one file under the job's prefix. Returns its size in bytes."""
    key = job_prefix(job_id) + os.path.basename(path)
    try:
        _client().upload_file(path, bucket(), key, ExtraArgs={"ContentType": _content_type(path)})
    except Exception as e:
        raise ArchiveError(f"upload of {os.path.basename(path)} failed: {e}") from e
    return os.path.getsize(path)


def archive_job(job_id: str, directory: str) -> dict:
    """Upload every archivable file. All or nothing as far as the caller is concerned: any failure
    raises, and the project is then simply not marked archived (the next attempt starts over;
    re-uploading the same keys is harmless)."""
    if not enabled():
        raise ArchiveError("archive storage is not configured")
    files = select_files(directory)
    if not any(f.endswith(".mp4") for f in files):
        raise ArchiveError("nothing to archive")
    total = sum(upload_file(job_id, f) for f in files)
    return {"files": len(files), "bytes": total}


def list_keys(job_id: str) -> List[str]:
    prefix = job_prefix(job_id)
    keys = []
    try:
        paginator = _client().get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket(), Prefix=prefix):
            keys.extend(o["Key"] for o in page.get("Contents", []))
    except Exception as e:
        raise ArchiveError(f"listing failed: {e}") from e
    return keys


def restore_job(job_id: str, directory: str) -> int:
    """Download a job into ``directory`` (created if missing). Files land in a sibling temp
    folder first, so a failure never leaves a half-restored job that looks complete."""
    keys = list_keys(job_id)
    if not keys:
        raise ArchiveError("no archived files")
    tmp = directory.rstrip("/\\") + ".restoring"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    client = _client()
    try:
        for key in keys:
            name = posixpath.basename(key)
            if not name:
                continue
            client.download_file(bucket(), key, os.path.join(tmp, name))
    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        raise ArchiveError(f"download failed: {e}") from e
    os.makedirs(directory, exist_ok=True)
    for name in os.listdir(tmp):
        shutil.move(os.path.join(tmp, name), os.path.join(directory, name))
    shutil.rmtree(tmp, ignore_errors=True)
    return len(keys)


def delete_job(job_id: str) -> int:
    """Remove a job's objects. Returns how many were deleted. A no-op when storage is off."""
    if not enabled():
        return 0
    keys = list_keys(job_id)
    client = _client()
    try:
        for i in range(0, len(keys), 500):
            client.delete_objects(Bucket=bucket(),
                                  Delete={"Objects": [{"Key": k} for k in keys[i:i + 500]], "Quiet": True})
    except Exception as e:
        raise ArchiveError(f"delete failed: {e}") from e
    return len(keys)


# ---- the project row -----------------------------------------------------------------------------
def state_of(row) -> dict:
    """What the UI needs: ``none`` (never archived), ``available`` or ``expired``."""
    archived, expires = row["archived_at"], row["archive_expires_at"]
    now = db.now()
    if archived and (expires is None or expires > now):
        state = "available"
    elif expires is not None and expires <= now:
        state = "expired"
    else:
        state = "none"
    return {"state": state, "expires_at": expires, "bytes": int(row["archive_bytes"] or 0)}


def mark_archived(job_id: str, nbytes: int, days: int) -> None:
    now = db.now()
    with db.connection() as conn:
        conn.execute("UPDATE projects SET archived_at = ?, archive_bytes = ?, archive_expires_at = ?, "
                     "updated_at = ? WHERE job_id = ?", (now, int(nbytes), now + days * 86400, now, job_id))


def is_restorable(job_id: str) -> bool:
    """True when storage is on and this project has unexpired archived files."""
    if not enabled():
        return False
    with db.connection() as conn:
        row = conn.execute("SELECT archived_at, archive_expires_at FROM projects WHERE job_id = ?",
                           (job_id,)).fetchone()
    return bool(row and row["archived_at"] and (row["archive_expires_at"] or 0) > db.now())


def owner_of(job_id: str) -> Optional[int]:
    with db.connection() as conn:
        row = conn.execute("SELECT user_id FROM projects WHERE job_id = ?", (job_id,)).fetchone()
    return int(row["user_id"]) if row else None


def purge_expired(limit: int = 50) -> int:
    """Delete the objects of projects whose retention ended. Run from the cleanup loop."""
    if not enabled():
        return 0
    with db.connection() as conn:
        rows = conn.execute("SELECT job_id FROM projects WHERE archived_at IS NOT NULL "
                            "AND archive_expires_at IS NOT NULL AND archive_expires_at <= ? LIMIT ?",
                            (db.now(), limit)).fetchall()
    purged = 0
    for r in rows:
        try:
            delete_job(r["job_id"])
        except ArchiveError as e:
            log.warning("purge of %s failed, will retry: %s", r["job_id"], e)
            continue
        with db.connection() as conn:
            conn.execute("UPDATE projects SET archived_at = NULL, archive_bytes = 0 WHERE job_id = ?",
                         (r["job_id"],))
        purged += 1
    return purged


def stats() -> dict:
    """For the admin overview."""
    with db.connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS n, COALESCE(SUM(archive_bytes),0) AS b FROM projects "
                           "WHERE archived_at IS NOT NULL").fetchone()
    return {"enabled": enabled(), "projects": row["n"], "bytes": int(row["b"])}
