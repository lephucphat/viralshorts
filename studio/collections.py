"""Named folders for the project library. Everything is scoped to the owner."""

import sqlite3
from typing import List, Optional

from . import db

MAX_PER_USER = 50
NAME_MAX = 60


class CollectionError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _clean(name: str) -> str:
    name = " ".join((name or "").split())[:NAME_MAX]
    if not name:
        raise CollectionError("name_required", "Give the collection a name.")
    return name


def _public(row, count: int) -> dict:
    return {"id": row["id"], "name": row["name"], "created_at": row["created_at"], "count": count}


def list_for_user(user_id: int) -> List[dict]:
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT c.*, (SELECT COUNT(*) FROM collection_projects cp WHERE cp.collection_id = c.id) AS n "
            "FROM collections c WHERE c.user_id = ? ORDER BY c.name COLLATE NOCASE", (user_id,)).fetchall()
    return [_public(r, r["n"]) for r in rows]


def create(user_id: int, name: str) -> dict:
    name = _clean(name)
    with db.connection() as conn:
        if conn.execute("SELECT COUNT(*) AS n FROM collections WHERE user_id = ?",
                        (user_id,)).fetchone()["n"] >= MAX_PER_USER:
            raise CollectionError("too_many", f"You can have up to {MAX_PER_USER} collections.")
        try:
            cur = conn.execute("INSERT INTO collections (user_id, name, created_at) VALUES (?,?,?)",
                               (user_id, name, db.now()))
        except sqlite3.IntegrityError:
            raise CollectionError("exists", "You already have a collection with that name.")
        row = conn.execute("SELECT * FROM collections WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _public(row, 0)


def rename(user_id: int, collection_id: int, name: str) -> Optional[dict]:
    name = _clean(name)
    with db.connection() as conn:
        try:
            cur = conn.execute("UPDATE collections SET name = ? WHERE id = ? AND user_id = ?",
                               (name, collection_id, user_id))
        except sqlite3.IntegrityError:
            raise CollectionError("exists", "You already have a collection with that name.")
        if cur.rowcount == 0:
            return None
    return next((c for c in list_for_user(user_id) if c["id"] == collection_id), None)


def delete(user_id: int, collection_id: int) -> bool:
    with db.connection() as conn:
        return conn.execute("DELETE FROM collections WHERE id = ? AND user_id = ?",
                            (collection_id, user_id)).rowcount > 0


def _owned_project_id(conn, user_id: int, job_id: str) -> Optional[int]:
    row = conn.execute("SELECT id FROM projects WHERE job_id = ? AND user_id = ?",
                       (job_id, user_id)).fetchone()
    return row["id"] if row else None


def add(user_id: int, collection_id: int, job_id: str) -> bool:
    """False when the collection or the project is not this user's."""
    with db.connection() as conn:
        pid = _owned_project_id(conn, user_id, job_id)
        owned = conn.execute("SELECT 1 FROM collections WHERE id = ? AND user_id = ?",
                             (collection_id, user_id)).fetchone()
        if pid is None or owned is None:
            return False
        conn.execute("INSERT OR IGNORE INTO collection_projects (collection_id, project_id, added_at) "
                     "VALUES (?,?,?)", (collection_id, pid, db.now()))
    return True


def remove(user_id: int, collection_id: int, job_id: str) -> bool:
    with db.connection() as conn:
        pid = _owned_project_id(conn, user_id, job_id)
        if pid is None:
            return False
        conn.execute("DELETE FROM collection_projects WHERE collection_id = ? AND project_id = ? "
                     "AND collection_id IN (SELECT id FROM collections WHERE user_id = ?)",
                     (collection_id, pid, user_id))
    return True


def for_project(user_id: int, job_id: str) -> List[int]:
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT cp.collection_id FROM collection_projects cp "
            "JOIN projects p ON p.id = cp.project_id WHERE p.job_id = ? AND p.user_id = ?",
            (job_id, user_id)).fetchall()
    return [r["collection_id"] for r in rows]
