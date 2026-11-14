"""Recipes: a person's saved create-project settings. Everything is scoped to the owner."""

import json
import sqlite3
from typing import List, Optional

from . import db

MAX_PER_USER = 20
NAME_MAX = 40
# The only keys a recipe may hold, each with its kind. Anything else in a request is dropped, and a
# value of the wrong kind is dropped too, so the stored JSON is always safe to feed back to the form.
ALLOWED = {
    "genre": "str", "language": "str", "clipLength": "str", "keywords": "str",
    "targetClips": "str", "outputFormat": "str", "layout": "str", "kitId": "str",
    "captions": "bool", "autoHook": "bool",
}
VALUE_MAX = 200


class RecipeError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _clean_name(name: str) -> str:
    name = " ".join((name or "").split())[:NAME_MAX]
    if not name:
        raise RecipeError("name_required", "Give the recipe a name.")
    return name


def clean_settings(raw) -> dict:
    out = {}
    if not isinstance(raw, dict):
        return out
    for key, kind in ALLOWED.items():
        if key not in raw:
            continue
        value = raw[key]
        if kind == "bool" and isinstance(value, bool):
            out[key] = value
        elif kind == "str" and isinstance(value, (str, int)) and not isinstance(value, bool):
            out[key] = str(value).strip()[:VALUE_MAX]
    return out


def _public(row) -> dict:
    try:
        settings = json.loads(row["settings"])
    except (TypeError, ValueError):
        settings = {}
    return {"id": row["id"], "name": row["name"], "settings": clean_settings(settings),
            "created_at": row["created_at"]}


def list_for_user(user_id: int) -> List[dict]:
    with db.connection() as conn:
        rows = conn.execute("SELECT * FROM recipes WHERE user_id = ? ORDER BY name COLLATE NOCASE",
                            (user_id,)).fetchall()
    return [_public(r) for r in rows]


def create(user_id: int, name: str, settings) -> dict:
    name = _clean_name(name)
    payload = json.dumps(clean_settings(settings), ensure_ascii=False)
    with db.connection() as conn:
        if conn.execute("SELECT COUNT(*) AS n FROM recipes WHERE user_id = ?",
                        (user_id,)).fetchone()["n"] >= MAX_PER_USER:
            raise RecipeError("too_many", f"You can keep up to {MAX_PER_USER} recipes.")
        try:
            cur = conn.execute("INSERT INTO recipes (user_id, name, settings, created_at) VALUES (?,?,?,?)",
                               (user_id, name, payload, db.now()))
        except sqlite3.IntegrityError:
            raise RecipeError("exists", "You already have a recipe with that name.")
        row = conn.execute("SELECT * FROM recipes WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _public(row)


def delete(user_id: int, recipe_id: int) -> bool:
    with db.connection() as conn:
        return conn.execute("DELETE FROM recipes WHERE id = ? AND user_id = ?",
                            (recipe_id, user_id)).rowcount > 0


def get(user_id: int, recipe_id: int) -> Optional[dict]:
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM recipes WHERE id = ? AND user_id = ?",
                           (recipe_id, user_id)).fetchone()
    return _public(row) if row else None
