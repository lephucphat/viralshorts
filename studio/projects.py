"""The project library: one row per job, scoped to its owner."""

import json
from typing import Optional

from . import archive, db

ACTIVE = ("queued", "processing")
TERMINAL = ("completed", "failed", "cancelled")
SORTS = {
    "newest": "created_at DESC",
    "oldest": "created_at ASC",
    "score": "COALESCE(top_score, -1) DESC, created_at DESC",
    "title": "title COLLATE NOCASE ASC",
}


def _public(row) -> dict:
    try:
        options = json.loads(row["options"] or "{}")
    except ValueError:
        options = {}
    return {
        "id": row["id"], "job_id": row["job_id"], "title": row["title"],
        "source_kind": row["source_kind"], "source_ref": row["source_ref"],
        "status": row["status"], "duration_seconds": row["duration_seconds"],
        "clip_count": row["clip_count"], "top_score": row["top_score"],
        "cover_url": row["cover_url"], "options": options,
        "minutes_charged": row["minutes_charged"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
        "finished_at": row["finished_at"],
        "favorite": bool(row["favorite"]),
        "archive": archive.state_of(row),
    }


def create(job_id: str, user_id: int, title: str, source_kind: str, source_ref: str = "",
           duration_seconds: float = 0.0, options: Optional[dict] = None) -> dict:
    now = db.now()
    with db.connection() as conn:
        conn.execute(
            "INSERT INTO projects (job_id, user_id, title, source_kind, source_ref, "
            "duration_seconds, options, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (job_id, user_id, (title or "").strip()[:200] or "Untitled", source_kind,
             (source_ref or "")[:500], float(duration_seconds or 0),
             json.dumps(options or {}, ensure_ascii=False), now, now))
        row = conn.execute("SELECT * FROM projects WHERE job_id = ?", (job_id,)).fetchone()
    return _public(row)


def get_by_job(job_id: str) -> Optional[dict]:
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM projects WHERE job_id = ?", (job_id,)).fetchone()
    return _public(row) if row else None


def get_for_user(user_id: int, job_id: str) -> Optional[dict]:
    """None when the project is missing OR belongs to someone else (same answer)."""
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM projects WHERE job_id = ? AND user_id = ?",
                           (job_id, user_id)).fetchone()
    return _public(row) if row else None


def list_for_user(user_id: int, q: str = "", status: str = "", sort: str = "newest",
                  limit: int = 60, offset: int = 0, favorite: bool = False,
                  collection_id: Optional[int] = None) -> dict:
    where, params = ["user_id = ?"], [user_id]
    if favorite:
        where.append("favorite = 1")
    if collection_id is not None:
        where.append("id IN (SELECT cp.project_id FROM collection_projects cp "
                     "JOIN collections c ON c.id = cp.collection_id "
                     "WHERE cp.collection_id = ? AND c.user_id = ?)")
        params.extend([int(collection_id), user_id])
    if q:
        where.append("title LIKE ? ESCAPE '\\'")
        like = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params.append(f"%{like}%")
    if status == "active":
        where.append("status IN ('queued','processing')")
    elif status in TERMINAL:
        where.append("status = ?")
        params.append(status)
    order = SORTS.get(sort, SORTS["newest"])
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    with db.connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS n FROM projects WHERE {' AND '.join(where)}",
                             params).fetchone()["n"]
        rows = conn.execute(
            f"SELECT * FROM projects WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ? OFFSET ?",
            (*params, limit, offset)).fetchall()
    return {"total": total, "items": [_public(r) for r in rows]}


def rename(user_id: int, job_id: str, title: str) -> Optional[dict]:
    title = (title or "").strip()[:200]
    if not title:
        return None
    with db.connection() as conn:
        cur = conn.execute("UPDATE projects SET title = ?, updated_at = ? "
                           "WHERE job_id = ? AND user_id = ?", (title, db.now(), job_id, user_id))
        if cur.rowcount == 0:
            return None
    return get_for_user(user_id, job_id)


def set_favorite(user_id: int, job_id: str, favorite: bool) -> Optional[dict]:
    with db.connection() as conn:
        cur = conn.execute("UPDATE projects SET favorite = ? WHERE job_id = ? AND user_id = ?",
                           (1 if favorite else 0, job_id, user_id))
        if cur.rowcount == 0:
            return None
    return get_for_user(user_id, job_id)


def set_status(job_id: str, status: str) -> None:
    fields = "status = ?, updated_at = ?"
    params = [status, db.now()]
    if status in TERMINAL:
        fields += ", finished_at = ?"
        params.append(db.now())
    with db.connection() as conn:
        conn.execute(f"UPDATE projects SET {fields} WHERE job_id = ?", (*params, job_id))


def finish(job_id: str, status: str, clip_count: int = 0, top_score: Optional[int] = None,
           cover_url: Optional[str] = None, duration_seconds: Optional[float] = None,
           title: Optional[str] = None, minutes_charged: int = 0) -> None:
    sets = ["status = ?", "clip_count = ?", "top_score = ?", "updated_at = ?",
            "finished_at = ?", "minutes_charged = ?"]
    params = [status, int(clip_count), top_score, db.now(), db.now(), int(minutes_charged)]
    if cover_url is not None:
        sets.append("cover_url = ?")
        params.append(cover_url)
    if duration_seconds:
        sets.append("duration_seconds = ?")
        params.append(float(duration_seconds))
    if title:
        # Only fill in a title the user has not chosen themselves: the placeholder
        # written at creation is replaced, an edited one never is.
        sets.append("title = CASE WHEN title IN ('', 'Untitled') OR title = source_ref "
                    "THEN ? ELSE title END")
        params.append(title[:200])
    with db.connection() as conn:
        conn.execute(f"UPDATE projects SET {', '.join(sets)} WHERE job_id = ?", (*params, job_id))


def delete(user_id: int, job_id: str) -> Optional[dict]:
    """Delete the row and return what it was (None if it was not this user's)."""
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM projects WHERE job_id = ? AND user_id = ?",
                           (job_id, user_id)).fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM projects WHERE id = ?", (row["id"],))
    return _public(row)


def job_ids_for_user(user_id: int) -> list:
    with db.connection() as conn:
        return [r["job_id"] for r in conn.execute(
            "SELECT job_id FROM projects WHERE user_id = ?", (user_id,)).fetchall()]
