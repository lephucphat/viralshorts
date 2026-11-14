"""Brand kits: the logo, colours and defaults applied to every clip of a job."""

import io
import os
import re
import uuid
from typing import Optional

from . import db

LOGO_POSITIONS = ("top-left", "top-right", "bottom-left", "bottom-right")
LAYOUTS = ("auto", "split", "screencast", "none")
OUTPUT_FORMATS = ("vertical", "square", "horizontal")
HOOK_STYLES = ("classic", "dark", "yellow", "red", "outline", "outline_yellow")
CAPTION_PRESETS = ("tiktok", "reels", "shorts", "gold", "neon", "cyber", "karaoke",
                   "minimal", "beast", "boxed", "classic")
MAX_KITS_PER_USER = 20
MAX_LOGO_BYTES = 2 * 1024 * 1024
MAX_LOGO_PIXELS = 4096
_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class KitError(Exception):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def logo_dir(user_id: int) -> str:
    return os.path.join(db.data_dir(), "brand", str(user_id))


def _public(row) -> dict:
    return {
        "id": row["id"], "name": row["name"], "has_logo": bool(row["logo_path"]),
        "logo_position": row["logo_position"], "logo_opacity": row["logo_opacity"],
        "logo_scale": row["logo_scale"], "primary_color": row["primary_color"],
        "secondary_color": row["secondary_color"], "caption_preset": row["caption_preset"],
        "hook_style": row["hook_style"], "layout": row["layout"],
        "output_format": row["output_format"], "is_default": bool(row["is_default"]),
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


def _validate(data: dict) -> dict:
    """Return the cleaned subset of fields, raising KitError on bad input."""
    out = {}
    if "name" in data:
        name = (data["name"] or "").strip()
        if not name or len(name) > 60:
            raise KitError("invalid_name", "Name must be 1-60 characters.")
        out["name"] = name
    choices = {
        "logo_position": LOGO_POSITIONS, "layout": LAYOUTS, "output_format": OUTPUT_FORMATS,
        "hook_style": HOOK_STYLES, "caption_preset": CAPTION_PRESETS,
    }
    for key, allowed in choices.items():
        if key in data:
            if data[key] not in allowed:
                raise KitError(f"invalid_{key}", f"{key} must be one of: {', '.join(allowed)}.")
            out[key] = data[key]
    for key in ("primary_color", "secondary_color"):
        if key in data:
            if not isinstance(data[key], str) or not _COLOR_RE.match(data[key]):
                raise KitError(f"invalid_{key}", f"{key} must be a #RRGGBB colour.")
            out[key] = data[key].upper()
    ranges = {"logo_opacity": (0.1, 1.0), "logo_scale": (0.05, 0.4)}
    for key, (lo, hi) in ranges.items():
        if key in data:
            try:
                val = float(data[key])
            except (TypeError, ValueError):
                raise KitError(f"invalid_{key}", f"{key} must be a number.")
            if not lo <= val <= hi:
                raise KitError(f"invalid_{key}", f"{key} must be between {lo} and {hi}.")
            out[key] = val
    return out


def list_for_user(user_id: int) -> list:
    with db.connection() as conn:
        rows = conn.execute("SELECT * FROM brand_kits WHERE user_id = ? "
                            "ORDER BY is_default DESC, created_at ASC", (user_id,)).fetchall()
    return [_public(r) for r in rows]


def get_for_user(user_id: int, kit_id: int) -> Optional[dict]:
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM brand_kits WHERE id = ? AND user_id = ?",
                           (kit_id, user_id)).fetchone()
    return _public(row) if row else None


def logo_path_for_user(user_id: int, kit_id: int) -> Optional[str]:
    with db.connection() as conn:
        row = conn.execute("SELECT logo_path FROM brand_kits WHERE id = ? AND user_id = ?",
                           (kit_id, user_id)).fetchone()
    path = row["logo_path"] if row else None
    return path if path and os.path.exists(path) else None


def logo_path_any(kit_id: int) -> Optional[str]:
    """For signed media URLs, where the signature (not a session) proves access."""
    with db.connection() as conn:
        row = conn.execute("SELECT logo_path FROM brand_kits WHERE id = ?", (kit_id,)).fetchone()
    path = row["logo_path"] if row else None
    return path if path and os.path.exists(path) else None


def create(user_id: int, data: dict) -> dict:
    cleaned = _validate({"name": "My brand", **data})
    now = db.now()
    with db.connection() as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM brand_kits WHERE user_id = ?",
                             (user_id,)).fetchone()["n"]
        if count >= MAX_KITS_PER_USER:
            raise KitError("too_many", f"You can keep up to {MAX_KITS_PER_USER} brand kits.", 409)
        cols = ["user_id", "created_at", "updated_at", *cleaned.keys()]
        vals = [user_id, now, now, *cleaned.values()]
        # The first kit a user makes becomes their default automatically.
        if count == 0:
            cols.append("is_default")
            vals.append(1)
        cur = conn.execute(
            f"INSERT INTO brand_kits ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", vals)
        row = conn.execute("SELECT * FROM brand_kits WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _public(row)


def update(user_id: int, kit_id: int, data: dict) -> Optional[dict]:
    cleaned = _validate(data)
    with db.connection() as conn:
        if conn.execute("SELECT 1 FROM brand_kits WHERE id = ? AND user_id = ?",
                        (kit_id, user_id)).fetchone() is None:
            return None
        if "is_default" in data and data["is_default"]:
            conn.execute("UPDATE brand_kits SET is_default = 0 WHERE user_id = ?", (user_id,))
            cleaned["is_default"] = 1
        if cleaned:
            sets = ", ".join(f"{k} = ?" for k in cleaned)
            conn.execute(f"UPDATE brand_kits SET {sets}, updated_at = ? WHERE id = ?",
                         (*cleaned.values(), db.now(), kit_id))
    return get_for_user(user_id, kit_id)


def delete(user_id: int, kit_id: int) -> bool:
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM brand_kits WHERE id = ? AND user_id = ?",
                           (kit_id, user_id)).fetchone()
        if row is None:
            return False
        conn.execute("DELETE FROM brand_kits WHERE id = ?", (kit_id,))
        if row["is_default"]:
            # Hand the default to the oldest remaining kit so there is always one.
            nxt = conn.execute("SELECT id FROM brand_kits WHERE user_id = ? "
                               "ORDER BY created_at ASC LIMIT 1", (user_id,)).fetchone()
            if nxt:
                conn.execute("UPDATE brand_kits SET is_default = 1 WHERE id = ?", (nxt["id"],))
    _remove_file(row["logo_path"])
    return True


def _remove_file(path: Optional[str]) -> None:
    if path:
        try:
            os.remove(path)
        except OSError:
            pass


def save_logo(user_id: int, kit_id: int, raw: bytes) -> Optional[dict]:
    """Validate an uploaded image and store it as a PNG; replaces any earlier logo.

    The bytes are decoded and re-encoded with Pillow: that rejects anything that
    is not really an image (an HTML file renamed .png) and strips metadata.
    """
    if len(raw) > MAX_LOGO_BYTES:
        raise KitError("logo_too_large", "Logo must be 2 MB or smaller.", 413)
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception:
        raise KitError("invalid_logo", "That file is not a valid image (PNG, JPG or WebP).")
    if max(img.size) > MAX_LOGO_PIXELS:
        raise KitError("invalid_logo", f"Logo must be at most {MAX_LOGO_PIXELS}px on its longest side.")
    img = img.convert("RGBA")
    with db.connection() as conn:
        row = conn.execute("SELECT logo_path FROM brand_kits WHERE id = ? AND user_id = ?",
                           (kit_id, user_id)).fetchone()
        if row is None:
            return None
        folder = logo_dir(user_id)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{uuid.uuid4().hex}.png")
        img.save(path, format="PNG")
        conn.execute("UPDATE brand_kits SET logo_path = ?, updated_at = ? WHERE id = ?",
                     (path, db.now(), kit_id))
    _remove_file(row["logo_path"])
    return get_for_user(user_id, kit_id)


def remove_logo(user_id: int, kit_id: int) -> Optional[dict]:
    with db.connection() as conn:
        row = conn.execute("SELECT logo_path FROM brand_kits WHERE id = ? AND user_id = ?",
                           (kit_id, user_id)).fetchone()
        if row is None:
            return None
        conn.execute("UPDATE brand_kits SET logo_path = NULL, updated_at = ? WHERE id = ?",
                     (db.now(), kit_id))
    _remove_file(row["logo_path"])
    return get_for_user(user_id, kit_id)


def resolve_for_job(user_id: int, kit_id: Optional[int]) -> Optional[dict]:
    """The kit a new job should use: the requested one, else the user's default.

    Returns the public fields plus ``logo_file`` (absolute path or None), which
    is what the pipeline needs to burn the logo in.
    """
    with db.connection() as conn:
        if kit_id:
            row = conn.execute("SELECT * FROM brand_kits WHERE id = ? AND user_id = ?",
                               (kit_id, user_id)).fetchone()
        else:
            row = conn.execute("SELECT * FROM brand_kits WHERE user_id = ? AND is_default = 1",
                               (user_id,)).fetchone()
    if row is None:
        return None
    kit = _public(row)
    path = row["logo_path"]
    kit["logo_file"] = path if path and os.path.exists(path) else None
    return kit
