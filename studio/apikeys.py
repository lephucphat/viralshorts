"""API keys for the programmatic API and the MCP endpoint (``Authorization: Bearer vsk_...``).

Only the sha256 of a key is stored, so a database leak does not hand out working keys; the
full key is shown once, when it is created. In paid mode a key only works while the owner's
plan includes ``api_access`` (a downgrade turns the keys off without deleting them), and a
locked or deleted account's keys stop at once.
"""

import hashlib
import secrets
from typing import List, Optional

from . import auth, db

PREFIX = "vsk_"
MAX_KEYS = 10


class ApiKeyError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create(user_id: int, name: str = "") -> dict:
    """A new key. The returned ``key`` is the only time the secret is visible."""
    name = (name or "").strip()[:60] or "API key"
    with db.write_connection() as conn:
        live = conn.execute("SELECT COUNT(*) FROM api_keys WHERE user_id = ? AND revoked_at IS NULL",
                            (user_id,)).fetchone()[0]
        if live >= MAX_KEYS:
            raise ApiKeyError("too_many_keys", f"You can have at most {MAX_KEYS} active keys. Revoke one first.", 409)
        raw = PREFIX + secrets.token_urlsafe(32)
        cur = conn.execute(
            "INSERT INTO api_keys (user_id, name, prefix, key_hash, created_at) VALUES (?,?,?,?,?)",
            (user_id, name, raw[:10], _hash(raw), db.now()))
    return {"id": cur.lastrowid, "name": name, "prefix": raw[:10], "created_at": db.now(),
            "last_used_at": None, "key": raw}


def list_for_user(user_id: int) -> List[dict]:
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT id, name, prefix, created_at, last_used_at FROM api_keys "
            "WHERE user_id = ? AND revoked_at IS NULL ORDER BY id DESC", (user_id,)).fetchall()
    return [dict(r) for r in rows]


def revoke(user_id: int, key_id: int) -> bool:
    with db.connection() as conn:
        cur = conn.execute("UPDATE api_keys SET revoked_at = ? WHERE id = ? AND user_id = ? "
                           "AND revoked_at IS NULL", (db.now(), key_id, user_id))
        return cur.rowcount == 1


def user_for_key(raw: str) -> Optional[auth.User]:
    """The account a key belongs to, or None (unknown, revoked, locked, or plan without API access)."""
    if not raw or not raw.startswith(PREFIX):
        return None
    with db.connection() as conn:
        row = conn.execute("SELECT id, user_id FROM api_keys WHERE key_hash = ? AND revoked_at IS NULL",
                           (_hash(raw),)).fetchone()
        if row is None:
            return None
        conn.execute("UPDATE api_keys SET last_used_at = ? WHERE id = ?", (db.now(), row["id"]))
    user = auth.get(int(row["user_id"]))
    if user is None or user.disabled:
        return None
    from . import plans
    if plans.paid_mode() and not plans.has_feature(user.plan, "api_access"):
        return None
    return user
