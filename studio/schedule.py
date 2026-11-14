"""The posting calendar: what a person planned to publish and when.

This table is the calendar's own record. The real queue lives at Upload-Post under the person's
own key (the browser holds it; we never see it), so a row only moves to ``scheduled`` when the
dashboard reports that Upload-Post accepted the post, and to ``published`` when the dashboard
sees it has left Upload-Post's pending list after its time. The server never claims more than
it was told.

Status flow:  planned -> scheduled -> published
              planned/failed -> scheduled | failed | cancelled      scheduled -> cancelled | failed
"""

import json
import math
import re
from typing import List, Optional

from . import db, projects

PLATFORMS = ("tiktok", "instagram", "youtube")
STATUSES = ("planned", "scheduled", "published", "failed", "cancelled")
# Where a row may go from each status. Terminal statuses have no way out.
_FLOW = {
    "planned": {"scheduled", "failed", "cancelled"},
    "failed": {"planned", "scheduled", "failed", "cancelled"},
    "scheduled": {"published", "cancelled", "failed"},
    "published": set(),
    "cancelled": set(),
}
_EDITABLE = ("planned", "failed")
MAX_RANGE_SECONDS = 62 * 86400
MAX_PER_USER = 1000
PAST_GRACE_SECONDS = 86400
MAX_AHEAD_SECONDS = 366 * 86400
_TZ = re.compile(r"[A-Za-z0-9_+\-]+(/[A-Za-z0-9_+\-]+){0,2}")


class ScheduleError(Exception):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def _view(row) -> dict:
    d = dict(row)
    try:
        d["platforms"] = json.loads(d.get("platforms") or "[]")
    except ValueError:
        d["platforms"] = []
    return d


def _clean_platforms(platforms) -> List[str]:
    if not isinstance(platforms, (list, tuple)):
        raise ScheduleError("bad_platforms", "Choose at least one network.")
    seen = []
    for p in platforms:
        if p not in PLATFORMS:
            raise ScheduleError("bad_platforms", "Unknown network.")
        if p not in seen:
            seen.append(p)
    if not seen:
        raise ScheduleError("bad_platforms", "Choose at least one network.")
    return seen


def _clean_time(value, now: float) -> float:
    try:
        when = float(value)
    except (TypeError, ValueError):
        raise ScheduleError("bad_time", "The date is not valid.")
    if not math.isfinite(when):
        raise ScheduleError("bad_time", "The date is not valid.")
    if when < now - PAST_GRACE_SECONDS:
        raise ScheduleError("past_date", "That date is already in the past.")
    if when > now + MAX_AHEAD_SECONDS:
        raise ScheduleError("too_far", "Plan at most a year ahead.")
    return when


def _clean_tz(tz) -> str:
    tz = (tz or "UTC").strip()
    if len(tz) > 64 or not _TZ.fullmatch(tz):
        raise ScheduleError("bad_timezone", "The time zone is not valid.")
    return tz


def get(user_id: int, post_id: int) -> Optional[dict]:
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM scheduled_posts WHERE id = ? AND user_id = ?",
                           (post_id, user_id)).fetchone()
    return _view(row) if row else None


def list_range(user_id: int, start, end) -> List[dict]:
    try:
        start, end = float(start), float(end)
    except (TypeError, ValueError):
        raise ScheduleError("bad_range", "The date range is not valid.")
    if not (math.isfinite(start) and math.isfinite(end)) or end <= start or end - start > MAX_RANGE_SECONDS:
        raise ScheduleError("bad_range", "The date range is not valid.")
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT * FROM scheduled_posts WHERE user_id = ? AND scheduled_for >= ? AND scheduled_for < ? "
            "ORDER BY scheduled_for, id LIMIT 500", (user_id, start, end)).fetchall()
    return [_view(r) for r in rows]


def create(user_id: int, job_id: str, clip_index, title: str, description: str,
           platforms, scheduled_for, tz: str = "UTC") -> dict:
    # Only the owner may plan a post for a project; a stranger's job id answers like a missing one.
    if projects.get_for_user(user_id, job_id or "") is None:
        raise ScheduleError("not_found", "Project not found.", 404)
    try:
        clip_index = int(clip_index)
    except (TypeError, ValueError):
        clip_index = -1
    if not 0 <= clip_index < 1000:
        raise ScheduleError("bad_clip", "The clip is not valid.")
    now = db.now()
    when = _clean_time(scheduled_for, now)
    plats = _clean_platforms(platforms)
    tz = _clean_tz(tz)
    with db.write_connection() as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM scheduled_posts WHERE user_id = ?", (user_id,)).fetchone()["n"]
        if n >= MAX_PER_USER:
            raise ScheduleError("too_many", "The calendar is full. Delete old posts first.", 409)
        cur = conn.execute(
            "INSERT INTO scheduled_posts (user_id, job_id, clip_index, title, description, platforms, "
            "scheduled_for, timezone, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (user_id, job_id, clip_index, (title or "").strip()[:200], (description or "").strip()[:2200],
             json.dumps(plats), when, tz, "planned", now, now))
        post_id = cur.lastrowid
    return get(user_id, post_id)


def update(user_id: int, post_id: int, fields: dict) -> dict:
    """Edit a post that has not been handed to Upload-Post (or failed on the way)."""
    post = get(user_id, post_id)
    if post is None:
        raise ScheduleError("not_found", "Post not found.", 404)
    if post["status"] not in _EDITABLE:
        raise ScheduleError("locked", "Cancel the scheduled post before changing it.", 409)
    sets, params = [], []
    now = db.now()
    if "scheduled_for" in fields:
        sets.append("scheduled_for = ?")
        params.append(_clean_time(fields["scheduled_for"], now))
    if "platforms" in fields:
        sets.append("platforms = ?")
        params.append(json.dumps(_clean_platforms(fields["platforms"])))
    if "timezone" in fields:
        sets.append("timezone = ?")
        params.append(_clean_tz(fields["timezone"]))
    if "title" in fields:
        sets.append("title = ?")
        params.append((fields["title"] or "").strip()[:200])
    if "description" in fields:
        sets.append("description = ?")
        params.append((fields["description"] or "").strip()[:2200])
    if not sets:
        return post
    if post["status"] == "failed":                  # edited after an error: ready to try again
        sets += ["status = 'planned'", "error = ''"]
    with db.write_connection() as conn:
        conn.execute(f"UPDATE scheduled_posts SET {', '.join(sets)}, updated_at = ? "
                     "WHERE id = ? AND user_id = ?", (*params, now, post_id, user_id))
    return get(user_id, post_id)


def set_status(user_id: int, post_id: int, status: str, vendor_job_id: Optional[str] = None,
               error: str = "") -> dict:
    """Record what the dashboard learned from Upload-Post."""
    if status not in STATUSES:
        raise ScheduleError("bad_status", "Unknown status.")
    post = get(user_id, post_id)
    if post is None:
        raise ScheduleError("not_found", "Post not found.", 404)
    if status != post["status"] and status not in _FLOW[post["status"]]:
        raise ScheduleError("bad_transition", f"A {post['status']} post cannot become {status}.", 409)
    vendor = (vendor_job_id or "").strip()[:120] or post["vendor_job_id"]
    with db.write_connection() as conn:
        conn.execute("UPDATE scheduled_posts SET status = ?, vendor_job_id = ?, error = ?, updated_at = ? "
                     "WHERE id = ? AND user_id = ?",
                     (status, vendor, (error or "")[:300] if status == "failed" else "",
                      db.now(), post_id, user_id))
    return get(user_id, post_id)


def delete(user_id: int, post_id: int) -> None:
    post = get(user_id, post_id)
    if post is None:
        raise ScheduleError("not_found", "Post not found.", 404)
    if post["status"] == "scheduled":
        # Upload-Post would still publish it: the queue entry has to be cancelled there first.
        raise ScheduleError("cancel_first", "Cancel the scheduled post first.", 409)
    with db.write_connection() as conn:
        conn.execute("DELETE FROM scheduled_posts WHERE id = ? AND user_id = ?", (post_id, user_id))


def export_rows(conn, user_id: int) -> list:
    rows = conn.execute("SELECT job_id, clip_index, title, platforms, scheduled_for, timezone, status, "
                        "created_at FROM scheduled_posts WHERE user_id = ? ORDER BY scheduled_for", (user_id,))
    return [dict(r) for r in rows]
