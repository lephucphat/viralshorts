"""In-app notifications (the bell). Rows hold only a kind, a reference and a little data; the
dashboard turns that into text in the reader's language, so nothing here is user-written prose.

``kind`` is a closed list. ``(user_id, kind, ref)`` is unique, so reporting the same event twice
(a retried hook, a restarted job) is harmless.
"""

import json
from datetime import datetime, timezone
from typing import List, Optional

from . import credits, db, plans

KINDS = ("clips_ready", "job_failed", "low_credits")
KEEP_PER_USER = 100
DATA_KEYS = ("title", "count")


def _clean_data(data) -> dict:
    out = {}
    if isinstance(data, dict):
        if "title" in data:
            out["title"] = " ".join(str(data["title"] or "").split())[:120]
        if "count" in data:
            try:
                out["count"] = max(0, int(data["count"]))
            except (TypeError, ValueError):
                pass
    return out


def add(user_id: int, kind: str, ref: str, data=None) -> bool:
    """Record an event once. False when the kind is unknown or the event was already recorded."""
    if kind not in KINDS or not ref:
        return False
    with db.connection() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO inbox (user_id, kind, ref, data, created_at) VALUES (?,?,?,?,?)",
            (user_id, kind, str(ref)[:80], json.dumps(_clean_data(data), ensure_ascii=False), db.now()))
        added = cur.rowcount == 1
        if added:   # keep the table small: only the newest KEEP_PER_USER rows survive
            conn.execute(
                "DELETE FROM inbox WHERE user_id = ? AND id NOT IN "
                "(SELECT id FROM inbox WHERE user_id = ? ORDER BY id DESC LIMIT ?)",
                (user_id, user_id, KEEP_PER_USER))
    return added


def _public(row) -> dict:
    try:
        data = json.loads(row["data"])
    except (TypeError, ValueError):
        data = {}
    return {"id": row["id"], "kind": row["kind"], "ref": row["ref"], "data": _clean_data(data),
            "read": row["read_at"] is not None, "created_at": row["created_at"]}


def list_for_user(user_id: int, limit: int = 30) -> dict:
    limit = max(1, min(int(limit), 100))
    with db.connection() as conn:
        rows = conn.execute("SELECT * FROM inbox WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                            (user_id, limit)).fetchall()
        unread = conn.execute("SELECT COUNT(*) AS n FROM inbox WHERE user_id = ? AND read_at IS NULL",
                              (user_id,)).fetchone()["n"]
    return {"items": [_public(r) for r in rows], "unread": unread}


def mark_read(user_id: int, item_id: Optional[int] = None) -> int:
    """Mark one item (or, with no id, everything) read. Returns how many rows changed."""
    sql = "UPDATE inbox SET read_at = ? WHERE user_id = ? AND read_at IS NULL"
    params: List = [db.now(), user_id]
    if item_id is not None:
        sql += " AND id = ?"
        params.append(int(item_id))
    with db.connection() as conn:
        return conn.execute(sql, params).rowcount


def job_finished(user_id: int, job_id: str, status: str, title: str = "", clip_count: int = 0) -> None:
    if status == "completed" and clip_count > 0:
        add(user_id, "clips_ready", job_id, {"title": title, "count": clip_count})
    elif status == "failed":
        add(user_id, "job_failed", job_id, {"title": title})


def low_credits(user_id: int) -> bool:
    """Same threshold as the email (10% of what they had, at least 5), once per month."""
    if not plans.paid_mode():
        return False
    bal = credits.balance(user_id)
    total = bal["plan_total"] + bal["topup_remaining"]
    if total <= 0 or bal["remaining"] > max(5, int(total * 0.1)):
        return False
    month = datetime.fromtimestamp(db.now(), tz=timezone.utc).strftime("%Y-%m")
    return add(user_id, "low_credits", month)
