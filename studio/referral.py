"""Friend referrals: a code per person, credits for both when the friend first pays.

A person's code is an ordinary row in ``promo_codes`` (note ``referral:<user id>``), so it can be
looked up, switched off or expired like any other code, but it can never be redeemed for credits
on its own (``promo.redeem`` refuses it). A new account attaches the code once; the link sits
``pending`` in ``referrals`` and pays out in the same transaction as the friend's FIRST paid
payment (``service.record_payment`` calls ``reward_first_payment``), so a replayed webhook cannot
pay twice. Both sides get the same credits as a never-expiring top-up, idempotent per referral.

Guards: no self-referral (same account or same inbox once Gmail dots and +tags are folded), only
before the friend has ever paid, one referrer per account, a ceiling on rewards per referrer,
and the same attempt throttle the promo box has. Switched off unless the paid edition runs and
``REFERRAL_REWARD_CREDITS`` is above zero.
"""

import os
import secrets
from typing import Optional

from . import auth, credits, db, plans, promo

DEFAULT_REWARD = 20
DEFAULT_MAX_REWARDS = 50
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"        # no 0/O/1/I/L: people read these aloud
NOTE_PREFIX = "referral:"


class ReferralError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def reward_credits() -> int:
    try:
        return max(0, int(os.environ.get("REFERRAL_REWARD_CREDITS", DEFAULT_REWARD)))
    except ValueError:
        return DEFAULT_REWARD


def max_rewards() -> int:
    try:
        return max(1, int(os.environ.get("REFERRAL_MAX_REWARDS", DEFAULT_MAX_REWARDS)))
    except ValueError:
        return DEFAULT_MAX_REWARDS


def enabled() -> bool:
    return plans.paid_mode() and reward_credits() > 0


def _note(user_id: int) -> str:
    return f"{NOTE_PREFIX}{int(user_id)}"


def code_for(user_id: int) -> str:
    """The person's referral code, created the first time it is asked for."""
    with db.connection() as conn:
        row = conn.execute("SELECT code FROM promo_codes WHERE note = ?", (_note(user_id),)).fetchone()
    if row:
        return row["code"]
    for _ in range(8):                               # a collision is astronomically rare, not impossible
        code = "VS-" + "".join(secrets.choice(_ALPHABET) for _ in range(7))
        try:
            promo.create(code, max(1, reward_credits()), note=_note(user_id))
            return code
        except promo.PromoError as e:
            if e.code != "code_exists":
                raise
            with db.connection() as conn:            # another request made this person's code first
                row = conn.execute("SELECT code FROM promo_codes WHERE note = ?", (_note(user_id),)).fetchone()
            if row:
                return row["code"]
    raise ReferralError("code_failed", "Could not create a code. Try again.", 503)


def _has_paid(conn, user_id: int) -> bool:
    return conn.execute("SELECT 1 FROM payments WHERE user_id = ? AND status IN ('paid','refunded','disputed') "
                        "LIMIT 1", (user_id,)).fetchone() is not None


def attach(user_id: int, code: str) -> dict:
    """Link this account to the person whose code it is. Generic errors on purpose: a guesser
    learns nothing about which codes exist."""
    if not enabled():
        raise ReferralError("referral_off", "Referrals are not available.", 404)
    auth.throttle(f"referral:{user_id}", 10, 3600)
    code = (code or "").strip()
    with db.write_connection() as conn:
        row = conn.execute("SELECT * FROM promo_codes WHERE code = ?", (code,)).fetchone()
        now = db.now()
        note = (row["note"] if row else "") or ""
        if (row is None or not note.startswith(NOTE_PREFIX) or not row["active"]
                or (row["expires_at"] and row["expires_at"] < now)):
            raise ReferralError("invalid_code", "That code is not valid.", 404)
        referrer_id = int(note[len(NOTE_PREFIX):])
        if referrer_id == user_id:
            raise ReferralError("own_code", "You cannot use your own code.", 409)
        if conn.execute("SELECT 1 FROM referrals WHERE referee_id = ?", (user_id,)).fetchone():
            raise ReferralError("already_referred", "A code is already linked to your account.", 409)
        if _has_paid(conn, user_id):
            raise ReferralError("already_customer", "Codes work for accounts that have not paid yet.", 409)
        pair = conn.execute("SELECT id, email_canonical FROM users WHERE id IN (?, ?)",
                            (user_id, referrer_id)).fetchall()
        canon = {r["id"]: r["email_canonical"] for r in pair}
        if referrer_id not in canon:
            raise ReferralError("invalid_code", "That code is not valid.", 404)
        if canon.get(user_id) and canon.get(user_id) == canon.get(referrer_id):
            raise ReferralError("own_code", "You cannot use your own code.", 409)
        conn.execute("INSERT INTO referrals (referrer_id, referee_id, code, status, created_at) "
                     "VALUES (?,?,?,?,?)", (referrer_id, user_id, row["code"], "pending", now))
    return status(user_id)


def reward_first_payment(conn, user_id: int) -> Optional[dict]:
    """Pay both sides if ``user_id`` was referred and has just made their first paid payment.
    Runs inside the payment's own transaction; returns what was paid, or None."""
    if not enabled():
        return None
    ref = conn.execute("SELECT * FROM referrals WHERE referee_id = ? AND status = 'pending'",
                       (user_id,)).fetchone()
    if ref is None:
        return None
    paid = conn.execute("SELECT COUNT(*) AS n FROM payments WHERE user_id = ? AND status = 'paid'",
                        (user_id,)).fetchone()["n"]
    if paid != 1:                                    # not the first one (or a refund beat us here)
        return None
    referrer = conn.execute("SELECT id, disabled_at FROM users WHERE id = ?", (ref["referrer_id"],)).fetchone()
    done = conn.execute("SELECT COUNT(*) AS n FROM referrals WHERE referrer_id = ? AND status = 'rewarded'",
                        (ref["referrer_id"],)).fetchone()["n"]
    amount = reward_credits()
    now = db.now()
    if referrer is None or referrer["disabled_at"] is not None or done >= max_rewards():
        # Nobody to pay (or the ceiling is reached): close the link without paying the friend a
        # reward the terms say depends on the referrer, rather than leave it pending forever.
        conn.execute("UPDATE referrals SET status = 'void', rewarded_at = ? WHERE id = ?", (now, ref["id"]))
        return None
    credits.grant(ref["referrer_id"], "topup", amount, expires_at=None,
                  source_ref=f"referral:{ref['id']}:referrer", conn=conn)
    credits.grant(user_id, "topup", amount, expires_at=None,
                  source_ref=f"referral:{ref['id']}:referee", conn=conn)
    conn.execute("UPDATE referrals SET status = 'rewarded', reward_credits = ?, rewarded_at = ? WHERE id = ?",
                 (amount, now, ref["id"]))
    conn.execute("UPDATE promo_codes SET used = used + 1 WHERE code = ?", (ref["code"],))
    return {"referrer_id": ref["referrer_id"], "referee_id": user_id, "credits": amount}


def status(user_id: int) -> dict:
    """Everything the account card shows."""
    on = enabled()
    out = {"enabled": on, "reward_credits": reward_credits() if on else 0, "code": None,
           "invited": 0, "rewarded": 0, "credits_earned": 0, "attached": None}
    if not on:
        return out
    out["code"] = code_for(user_id)
    with db.connection() as conn:
        rows = conn.execute("SELECT status, reward_credits FROM referrals WHERE referrer_id = ?",
                            (user_id,)).fetchall()
        mine = conn.execute("SELECT status, reward_credits FROM referrals WHERE referee_id = ?",
                            (user_id,)).fetchone()
        can_attach = mine is None and not _has_paid(conn, user_id)
    out["invited"] = len(rows)
    out["rewarded"] = sum(1 for r in rows if r["status"] == "rewarded")
    out["credits_earned"] = sum(int(r["reward_credits"]) for r in rows if r["status"] == "rewarded")
    out["attached"] = {"status": mine["status"], "reward_credits": int(mine["reward_credits"])} if mine else None
    out["can_attach"] = can_attach
    return out
