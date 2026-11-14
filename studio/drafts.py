"""Unfinished work in a standalone tool, kept as a draft the person can reopen, like a project.

The browser makes the draft id and saves the tool's state as it goes. Only a known list of keys is
stored (so the table is not a place to park arbitrary data), the size is capped, and the preview
may only point at a generated thumbnail path.
"""

import json
import re
from typing import Optional

from . import assets, db

KINDS = ("thumbnails",)
KEEP_PER_USER = 30
MAX_DATA_BYTES = 200_000
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,40}$")
DATA_KEYS = (
    "step", "mode", "sessionId", "titles", "selectedTitle", "manualTitle", "chatHistory",
    "recommended", "thumbnailTexts", "extraPrompt", "thumbnailCount", "burnText", "style",
    "generatedThumbnails", "description", "selectedThumbnail", "preprocessSessionId",
)


class DraftError(ValueError):
    pass


def valid_id(draft_id: str) -> bool:
    return bool(isinstance(draft_id, str) and _ID_RE.match(draft_id))


def _title(data: dict) -> str:
    return " ".join(str(data.get("selectedTitle") or data.get("manualTitle") or "").split())[:120]


def _preview(data: dict) -> str:
    cands = [data.get("selectedThumbnail")]
    for t in data.get("generatedThumbnails") or []:
        if isinstance(t, dict):
            cands.append(t.get("url"))
    return next((c for c in cands if assets.valid_url(c)), "")


def save(user_id: int, draft_id: str, kind: str, data: dict) -> None:
    if kind not in KINDS:
        raise DraftError("unknown_kind")
    if not valid_id(draft_id):
        raise DraftError("bad_id")
    if not isinstance(data, dict):
        raise DraftError("bad_data")
    clean = {k: data[k] for k in DATA_KEYS if k in data}
    try:
        step = max(0, min(int(clean.get("step") or 0), 9))
    except (TypeError, ValueError):
        step = 0
    if step == 0:
        raise DraftError("empty")      # nothing worth keeping yet
    blob = json.dumps(clean, ensure_ascii=False)
    if len(blob.encode("utf-8")) > MAX_DATA_BYTES:
        raise DraftError("too_big")
    now = db.now()
    with db.connection() as conn:
        conn.execute(
            "INSERT INTO tool_drafts (user_id, id, kind, title, step, preview, data, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(user_id, id) DO UPDATE SET "
            "title=excluded.title, step=excluded.step, preview=excluded.preview, "
            "data=excluded.data, updated_at=excluded.updated_at",
            (user_id, draft_id, kind, _title(clean), step, _preview(clean), blob, now))
        conn.execute(
            "DELETE FROM tool_drafts WHERE user_id = ? AND kind = ? AND id NOT IN "
            "(SELECT id FROM tool_drafts WHERE user_id = ? AND kind = ? "
            "ORDER BY updated_at DESC LIMIT ?)",
            (user_id, kind, user_id, kind, KEEP_PER_USER))


def list_for_user(user_id: int, kind: Optional[str] = None) -> list:
    sql = "SELECT id, kind, title, step, preview, updated_at FROM tool_drafts WHERE user_id = ?"
    params: list = [user_id]
    if kind in KINDS:
        sql += " AND kind = ?"
        params.append(kind)
    sql += " ORDER BY updated_at DESC LIMIT ?"
    params.append(KEEP_PER_USER)
    with db.connection() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get(user_id: int, draft_id: str) -> Optional[dict]:
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM tool_drafts WHERE user_id = ? AND id = ?",
                           (user_id, draft_id)).fetchone()
    if row is None:
        return None
    try:
        data = json.loads(row["data"])
    except (TypeError, ValueError):
        data = {}
    return {"id": row["id"], "kind": row["kind"], "title": row["title"], "step": row["step"],
            "updated_at": row["updated_at"], "data": data}


def delete(user_id: int, draft_id: str) -> bool:
    with db.connection() as conn:
        return conn.execute("DELETE FROM tool_drafts WHERE user_id = ? AND id = ?",
                            (user_id, draft_id)).rowcount > 0
