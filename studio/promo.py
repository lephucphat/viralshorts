"""Promo codes that hand out credits (campaigns, goodwill, a classmate's demo account).

A code is created by an admin and redeemed once per person. Credits arrive as a normal top-up
grant (never expire), idempotent per ``(code, user)`` so a double click cannot pay twice. Unknown,
expired, switched-off and used-up codes all answer the same way, so a guesser learns nothing.
"""

import re
from typing import Optional

from . import auth, credits, db

MAX_CREDITS = 100_000
_CODE = re.compile(r"[A-Za-z0-9_-]{3,32}")


class PromoError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def create(code: str, credit_amount: int, max_uses: int = 0, expires_at: Optional[float] = None,
           note: str = "") -> dict:
    code = (code or "").strip()
    if not _CODE.fullmatch(code):
        raise PromoError("bad_code", "A code is 3-32 letters, digits, - or _.", 422)
    if not 1 <= int(credit_amount) <= MAX_CREDITS:
        raise PromoError("bad_amount", f"Credits must be between 1 and {MAX_CREDITS}.", 422)
    with db.connection() as conn:
        if conn.execute("SELECT 1 FROM promo_codes WHERE code = ?", (code,)).fetchone():
            raise PromoError("code_exists", "That code already exists.", 409)
        conn.execute("INSERT INTO promo_codes (code, credits, max_uses, expires_at, note, created_at) "
                     "VALUES (?,?,?,?,?,?)",
                     (code, int(credit_amount), max(0, int(max_uses)), expires_at, (note or "")[:200], db.now()))
    return get(code)


def get(code: str) -> Optional[dict]:
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM promo_codes WHERE code = ?", ((code or "").strip(),)).fetchone()
    return dict(row) if row else None


def list_codes() -> list:
    with db.connection() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM promo_codes ORDER BY created_at DESC LIMIT 200")]


def set_active(code: str, active: bool) -> bool:
    with db.connection() as conn:
        return conn.execute("UPDATE promo_codes SET active = ? WHERE code = ?",
                            (1 if active else 0, (code or "").strip())).rowcount == 1


def redeem(user_id: int, code: str) -> int:
    """Give the user the code's credits. Returns how many."""
    auth.throttle(f"promo:{user_id}", 10, 3600)               # nobody guesses codes at speed
    code = (code or "").strip()
    with db.write_connection() as conn:
        row = conn.execute("SELECT * FROM promo_codes WHERE code = ?", (code,)).fetchone()
        now = db.now()
        if (row is None or not row["active"] or (row["expires_at"] and row["expires_at"] < now)
                or (row["max_uses"] and row["used"] >= row["max_uses"])
                or (row["note"] or "").startswith("referral:")):      # referral codes pay on a purchase, never here
            raise PromoError("invalid_code", "That code is not valid.", 404)
        if conn.execute("SELECT 1 FROM promo_redemptions WHERE code = ? AND user_id = ?",
                        (row["code"], user_id)).fetchone():
            raise PromoError("already_redeemed", "You have already used this code.", 409)
        conn.execute("INSERT INTO promo_redemptions (code, user_id, credits, redeemed_at) VALUES (?,?,?,?)",
                     (row["code"], user_id, row["credits"], now))
        conn.execute("UPDATE promo_codes SET used = used + 1 WHERE code = ?", (row["code"],))
        credits.grant(user_id, "topup", int(row["credits"]), expires_at=None,
                      source_ref=f"promo:{row['code'].lower()}:{user_id}", conn=conn)
        return int(row["credits"])
