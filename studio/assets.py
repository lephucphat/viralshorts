"""What the standalone tools made (thumbnails today), kept per user so it survives leaving the page.

The image file stays under ``output/``; a row here says whose it is and what it was for.
``url`` is the public path the file is served at (``/thumbnails/<session>/<file>``) and is
checked on the way in, because the row later decides which file gets deleted.
"""

import re
from typing import List, Optional, Tuple

from . import db

KINDS = ("thumbnail",)
KEEP_PER_USER = 150
_URL_RE = re.compile(r"^/thumbnails/[A-Za-z0-9_.\-]{1,80}/[A-Za-z0-9_.\-]{1,120}$")


def valid_url(url: str) -> bool:
    return bool(isinstance(url, str) and _URL_RE.match(url) and ".." not in url)


def _clip(value, n: int) -> str:
    return " ".join(str(value or "").split())[:n]


def add_many(user_id: int, kind: str, items: List[dict]) -> List[str]:
    """Remember ``items`` (each ``{url, title, text}``). Returns the urls of older rows that were
    dropped to respect ``KEEP_PER_USER``, so the caller can delete those files."""
    if kind not in KINDS:
        return []
    now = db.now()
    with db.connection() as conn:
        for it in items:
            url = it.get("url")
            if not valid_url(url):
                continue
            conn.execute(
                "INSERT OR IGNORE INTO tool_assets (user_id, kind, url, title, text, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (user_id, kind, url, _clip(it.get("title"), 200), _clip(it.get("text"), 80), now))
        old = conn.execute(
            "SELECT id, url FROM tool_assets WHERE user_id = ? AND kind = ? AND id NOT IN "
            "(SELECT id FROM tool_assets WHERE user_id = ? AND kind = ? ORDER BY id DESC LIMIT ?)",
            (user_id, kind, user_id, kind, KEEP_PER_USER)).fetchall()
        for r in old:
            conn.execute("DELETE FROM tool_assets WHERE id = ?", (r["id"],))
    return [r["url"] for r in old]


def list_for_user(user_id: int, kind: Optional[str] = None, limit: int = 60) -> List[dict]:
    limit = max(1, min(int(limit), 150))
    sql = "SELECT id, kind, url, title, text, created_at FROM tool_assets WHERE user_id = ?"
    params: list = [user_id]
    if kind:
        sql += " AND kind = ?"
        params.append(kind)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with db.connection() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def delete(user_id: int, asset_id: int) -> Optional[str]:
    """Forget one item. Returns its url (so the file can be removed) or None if it is not theirs."""
    with db.connection() as conn:
        row = conn.execute("SELECT url FROM tool_assets WHERE id = ? AND user_id = ?",
                           (int(asset_id), user_id)).fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM tool_assets WHERE id = ?", (int(asset_id),))
    return row["url"]


def urls_for_user(user_id: int) -> List[str]:
    with db.connection() as conn:
        return [r["url"] for r in conn.execute(
            "SELECT url FROM tool_assets WHERE user_id = ?", (user_id,)).fetchall()]


def split_url(url: str) -> Tuple[str, str]:
    """``/thumbnails/<session>/<file>`` -> (session, file)."""
    _, _, session, name = url.split("/", 3)
    return session, name
