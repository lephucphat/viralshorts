"""Account lifecycle by email: verify the inbox, reset a password, receipts, low-credit alerts.

Tokens are random, single-use and only their sha256 is stored, so a database leak does
not hand out working reset links. Every notification goes through ``_claim``: one
``(kind, ref)`` row is one email, so a webhook replay or a retry loop cannot send twice,
and a failed send releases the row so the next sweep tries again.
"""

import hashlib
import secrets
import threading
from datetime import datetime, timezone
from typing import Optional

from . import auth, credits, db, emailnorm, mailer, plans, security
from .payments import frontend_url

VERIFY_TTL = 3 * 24 * 3600
RESET_TTL = 3600
RECEIPT_WINDOW = 7 * 24 * 3600     # a receipt older than this is not worth sending any more


def background(fn, *args) -> None:
    """Run ``fn`` off the request thread (a slow SMTP server must not stall a webhook or a
    job callback). Tests set ``mailer.SYNC`` to run it inline."""
    def _run():
        try:
            fn(*args)
        except Exception:          # notifications are best effort by design
            mailer.log.exception("background notification failed")
    if mailer.SYNC:
        _run()
    else:
        threading.Thread(target=_run, daemon=True).start()


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# ---- tokens ---------------------------------------------------------------------------------
def create_token(user_id: int, kind: str, ttl: int, payload: Optional[str] = None) -> str:
    """A new token; any earlier unused one of the same kind stops working. ``payload`` rides
    along with the token (the new address of an email-change link)."""
    raw = secrets.token_urlsafe(32)
    with db.connection() as conn:
        conn.execute("DELETE FROM auth_tokens WHERE user_id = ? AND kind = ? AND used_at IS NULL",
                     (user_id, kind))
        conn.execute("INSERT INTO auth_tokens (user_id, kind, token_hash, expires_at, created_at, payload) "
                     "VALUES (?,?,?,?,?,?)", (user_id, kind, _hash(raw), db.now() + ttl, db.now(), payload))
    return raw


def _consume(conn, raw: str, kind: str) -> int:
    """Use a token once. Returns the user id or raises the same error for every failure."""
    now = db.now()
    cur = conn.execute(
        "UPDATE auth_tokens SET used_at = ? WHERE token_hash = ? AND kind = ? "
        "AND used_at IS NULL AND expires_at > ?", (now, _hash(raw or ""), kind, now))
    if cur.rowcount != 1:
        raise auth.AuthError("invalid_token", "This link is invalid or has expired.", 400)
    return int(conn.execute("SELECT user_id FROM auth_tokens WHERE token_hash = ?",
                            (_hash(raw),)).fetchone()["user_id"])


def _consume_payload(conn, raw: str, kind: str):
    """Like ``_consume`` but also returns the token's payload: ``(user_id, payload)``."""
    uid = _consume(conn, raw, kind)
    row = conn.execute("SELECT payload FROM auth_tokens WHERE token_hash = ?", (_hash(raw),)).fetchone()
    return uid, row["payload"]


def purge_expired_tokens(grace_seconds: int = 86400) -> int:
    """Delete emailed links that expired (or were used) more than a day ago."""
    cutoff = db.now() - grace_seconds
    with db.connection() as conn:
        return conn.execute("DELETE FROM auth_tokens WHERE expires_at < ? OR (used_at IS NOT NULL AND used_at < ?)",
                            (cutoff, cutoff)).rowcount


# ---- notifications (idempotent) -------------------------------------------------------------
def _claim(user_id: int, kind: str, ref: str) -> bool:
    with db.connection() as conn:
        cur = conn.execute("INSERT OR IGNORE INTO notifications (user_id, kind, ref, created_at) "
                           "VALUES (?,?,?,?)", (user_id, kind, ref, db.now()))
        return cur.rowcount == 1


def _release(kind: str, ref: str) -> None:
    with db.connection() as conn:
        conn.execute("DELETE FROM notifications WHERE kind = ? AND ref = ?", (kind, ref))


def _user_row(user_id: int):
    with db.connection() as conn:
        return conn.execute("SELECT id, email, name, lang FROM users WHERE id = ?", (user_id,)).fetchone()


def _name(row) -> str:
    return (row["name"] or row["email"].split("@")[0]).strip()


# ---- verify email ---------------------------------------------------------------------------
def send_verification(user_id: int) -> bool:
    """Email a confirmation link. No-op for a verified account or when mail is off."""
    if not mailer.enabled():
        return False
    row = _user_row(user_id)
    with db.connection() as conn:
        verified = conn.execute("SELECT email_verified_at FROM users WHERE id = ?",
                                (user_id,)).fetchone()
    if row is None or verified is None or verified["email_verified_at"] is not None:
        return False
    link = f"{frontend_url()}/#/verify?token={create_token(user_id, 'verify', VERIFY_TTL)}"
    subject, text, html = mailer.verify_message(row["lang"], _name(row), link)
    mailer.send_async(row["email"], subject, text, html)
    return True


def send_welcome(user_id: int) -> bool:
    """One welcome email per account (``_claim`` makes it idempotent). When verification is
    required it waits for the confirmed address, so a new person gets one email at a time."""
    if not mailer.enabled():
        return False
    row = _user_row(user_id)
    if row is None:
        return False
    if mailer.verification_required():
        with db.connection() as conn:
            verified = conn.execute("SELECT email_verified_at FROM users WHERE id = ?",
                                    (user_id,)).fetchone()
        if verified is None or verified["email_verified_at"] is None:
            return False
    if not _claim(user_id, "welcome", str(user_id)):
        return False
    link = f"{frontend_url()}/#/projects"
    subject, text, html = mailer.welcome_message(row["lang"], _name(row), link)
    if not mailer.send(row["email"], subject, text, html):
        _release("welcome", str(user_id))
        return False
    return True


def resend_verification_for(email: str, client_ip: str = "") -> None:
    """For someone whose link expired and who is not signed in. Always returns quietly: the
    answer must not reveal whether the address has an account. Throttled per address and client."""
    key = (email or "").strip().lower()
    if client_ip:
        auth.throttle(f"resend-ip:{client_ip}", 10, 3600)
    try:
        auth.throttle(f"resend-mail:{key}", 3, 3600)
    except auth.AuthError:
        return
    with db.connection() as conn:
        row = conn.execute("SELECT id FROM users WHERE email = ? AND disabled_at IS NULL", (key,)).fetchone()
    if row is not None:
        send_verification(int(row["id"]))


def verify_email(raw: str) -> auth.User:
    """Confirm an address from an emailed link: a first-time verification, or the new
    address of an email change (the same page handles both)."""
    with db.connection() as conn:
        kind = conn.execute("SELECT kind FROM auth_tokens WHERE token_hash = ?",
                            (_hash(raw or ""),)).fetchone()
    if kind is not None and kind["kind"] == "email_change":
        return _apply_email_change(raw)
    with db.connection() as conn:
        uid = _consume(conn, raw, "verify")
        conn.execute("UPDATE users SET email_verified_at = COALESCE(email_verified_at, ?) WHERE id = ?",
                     (db.now(), uid))
    user = auth.get(uid)
    # The free credits were withheld until now; grant them straight away.
    if plans.paid_mode():
        credits.ensure_free_grant(uid)
    background(send_welcome, uid)
    return user


# ---- change email ---------------------------------------------------------------------------
EMAIL_CHANGE_TTL = 3600


def request_email_change(user_id: int, new_email: str) -> None:
    """Step 1: mail a confirmation link to the NEW address. Nothing changes until it is used,
    so a typo or someone else's address never locks the owner out. The caller has already
    confirmed the owner's password."""
    new_email = auth.normalise_email(new_email)
    if emailnorm.is_disposable(new_email):
        raise auth.AuthError("disposable_email", "Please use a permanent email address.", 422)
    auth.throttle(f"email-change:{user_id}", 5, 3600)
    row = _user_row(user_id)
    if row is None:
        raise auth.AuthError("bad_credentials", "Account not found.", 404)
    if new_email == row["email"].lower():
        raise auth.AuthError("same_email", "That is already your email address.", 422)
    with db.connection() as conn:
        taken = conn.execute("SELECT 1 FROM users WHERE (email = ? OR email_canonical = ?) AND id != ?",
                             (new_email, emailnorm.canonical(new_email), user_id)).fetchone()
    if taken:
        raise auth.AuthError("email_taken", "An account with this email already exists.", 409)
    if not mailer.enabled():
        raise auth.AuthError("mail_off", "Email is not set up on this server, so the address cannot be changed.", 503)
    link = f"{frontend_url()}/#/verify?token={create_token(user_id, 'email_change', EMAIL_CHANGE_TTL, new_email)}"
    subject, text, html = mailer.email_change_message(row["lang"], _name(row), new_email, link)
    mailer.send_async(new_email, subject, text, html)


def _apply_email_change(raw: str) -> auth.User:
    with db.write_connection() as conn:
        uid, new_email = _consume_payload(conn, raw, "email_change")
        old = conn.execute("SELECT email, name, lang FROM users WHERE id = ?", (uid,)).fetchone()
        if not new_email or old is None:
            raise auth.AuthError("invalid_token", "This link is invalid or has expired.", 400)
        if conn.execute("SELECT 1 FROM users WHERE (email = ? OR email_canonical = ?) AND id != ?",
                        (new_email, emailnorm.canonical(new_email), uid)).fetchone():
            raise auth.AuthError("email_taken", "An account with this email already exists.", 409)
        # Following the link proves the new inbox. token_version + 1 signs out every device.
        conn.execute("UPDATE users SET email = ?, email_canonical = ?, "
                     "email_verified_at = ?, token_version = token_version + 1 WHERE id = ?",
                     (new_email, emailnorm.canonical(new_email), db.now(), uid))
    # Tell the old address, so a hijacked session cannot move the account silently.
    subject, text, html = mailer.email_changed_notice(old["lang"], (old["name"] or old["email"]).strip(), new_email)
    mailer.send_async(old["email"], subject, text, html)
    return auth.get(uid)


def send_password_changed(user_id: int) -> bool:
    """Tell the owner their password just changed (so an unexpected change is noticed)."""
    if not mailer.enabled():
        return False
    row = _user_row(user_id)
    if row is None:
        return False
    subject, text, html = mailer.password_changed_message(row["lang"], _name(row), f"{frontend_url()}/#/forgot")
    return mailer.send(row["email"], subject, text, html)


# ---- reset password -------------------------------------------------------------------------
def request_reset(email: str, client_ip: str = "") -> None:
    """Always returns quietly, whether or not the address has an account: the answer must not
    tell a stranger who is registered. Throttled per address and per client."""
    key = (email or "").strip().lower()
    if client_ip:
        auth.throttle(f"forgot-ip:{client_ip}", 10, 3600)
    try:
        auth.throttle(f"forgot:{key}", 3, 3600)
    except auth.AuthError:
        return
    with db.connection() as conn:
        row = conn.execute("SELECT id, email, name, lang, disabled_at FROM users WHERE email = ?",
                           (key,)).fetchone()
    if row is None or row["disabled_at"] is not None:
        return
    link = f"{frontend_url()}/#/reset?token={create_token(row['id'], 'reset', RESET_TTL)}"
    subject, text, html = mailer.reset_message(row["lang"], _name(row), link)
    mailer.send_async(row["email"], subject, text, html)


def reset_password(raw: str, new_password: str) -> auth.User:
    auth.check_password(new_password)
    with db.connection() as conn:
        uid = _consume(conn, raw, "reset")
        # token_version + 1 signs out every device that held the old password. Receiving
        # the link also proves the inbox, so the account counts as verified.
        conn.execute("UPDATE users SET password_hash = ?, token_version = token_version + 1, "
                     "email_verified_at = COALESCE(email_verified_at, ?) WHERE id = ?",
                     (security.hash_password(new_password), db.now(), uid))
        # Any other outstanding reset link is dead too.
        conn.execute("DELETE FROM auth_tokens WHERE user_id = ? AND kind = 'reset' AND used_at IS NULL", (uid,))
    return auth.get(uid)


# ---- account deletion -----------------------------------------------------------------------
def send_account_deleted(who: dict, subscription_cancelled: bool = False) -> bool:
    """Confirm a deletion to the address that owned the account. The account row is gone by
    now, so everything needed comes from ``who`` (email, name, lang)."""
    if not mailer.enabled() or not who.get("email"):
        return False
    name = (who.get("name") or who["email"].split("@")[0]).strip()
    subject, text, html = mailer.account_deleted_message(who.get("lang", "vi"), name, subscription_cancelled)
    return mailer.send(who["email"], subject, text, html)


# ---- receipts -------------------------------------------------------------------------------
def _money(amount: int, currency: str, lang: str) -> str:
    if currency.lower() == "vnd":
        return f"{amount:,.0f} ₫".replace(",", ".")
    return f"${amount / 100:,.2f}"


def send_pending_receipts() -> int:
    """Email a receipt for every paid payment that has none. Safe to call after every
    webhook and from the cleanup loop: a payment is claimed once, and a failed send is
    retried by the next call (until it is older than ``RECEIPT_WINDOW``)."""
    if not mailer.enabled():
        return 0
    sent = 0
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT p.id, p.user_id, p.kind, p.item, p.amount, p.currency, p.credits, p.paid_at, "
            "u.email, u.name, u.lang FROM payments p JOIN users u ON u.id = p.user_id "
            "WHERE p.status = 'paid' AND p.paid_at IS NOT NULL AND p.paid_at > ? "
            "AND NOT EXISTS (SELECT 1 FROM notifications n WHERE n.kind = 'receipt' AND n.ref = CAST(p.id AS TEXT))",
            (db.now() - RECEIPT_WINDOW,)).fetchall()
    for r in rows:
        ref = str(r["id"])
        if not _claim(r["user_id"], "receipt", ref):
            continue
        en = r["lang"] == "en"
        if r["kind"] == "topup":
            what = f"{r['credits']} credits" if en else f"{r['credits']} credit"
        else:
            plan = plans.get_plan(r["item"]).name
            what = f"the {plan} plan" if en else f"gói {plan}"
        date = datetime.fromtimestamp(r["paid_at"], tz=timezone.utc).strftime("%Y-%m-%d")
        subject, text, html = mailer.receipt_message(
            r["lang"], _name(r), what, _money(r["amount"], r["currency"], r["lang"]),
            r["credits"], date, f"{frontend_url()}/#/account")
        if mailer.send(r["email"], subject, text, html):
            sent += 1
        else:
            _release("receipt", ref)
    return sent


# ---- plan notices -----------------------------------------------------------------------------
EXPIRY_NOTICE_SECONDS = 3 * 24 * 3600


def send_billing_notices() -> int:
    """Emails about a plan's life, each sent once (the ``notifications`` claim):
    a failed card renewal, a prepaid plan ending within three days, and a plan that ended.
    Safe to call often (after webhooks and from the cleanup loop); a failed send is retried."""
    if not mailer.enabled():
        return 0
    from .payments import service           # late: payments imports this module
    service.expire_due_subscriptions()      # a plan that ran out is 'expired' before it is announced
    now = db.now()
    sent = 0
    with db.connection() as conn:
        failed = conn.execute(
            "SELECT s.id, s.user_id, s.plan, s.current_period_end FROM subscriptions s "
            "WHERE s.status = 'past_due'").fetchall()
        # the latest period end per user decides whether a prepaid plan is really about to lapse
        ending = conn.execute(
            "SELECT s.user_id, s.plan, MAX(s.current_period_end) AS ends FROM subscriptions s "
            "WHERE s.provider = 'payos' AND s.status = 'active' "
            "GROUP BY s.user_id HAVING MAX(s.current_period_end) > ? AND MAX(s.current_period_end) <= ?",
            (now, now + EXPIRY_NOTICE_SECONDS)).fetchall()
        ended = conn.execute(
            "SELECT s.user_id, s.plan, MAX(s.current_period_end) AS ends FROM subscriptions s "
            "WHERE s.provider = 'payos' GROUP BY s.user_id "
            "HAVING MAX(s.current_period_end) <= ? AND MAX(s.current_period_end) > ? "
            "AND NOT EXISTS (SELECT 1 FROM subscriptions a WHERE a.user_id = s.user_id AND a.status IN ('active','trialing','past_due'))",
            (now, now - EXPIRY_NOTICE_SECONDS)).fetchall()

    def _go(user_id, kind, ref, build):
        nonlocal sent
        row = _user_row(user_id)
        if row is None or not _claim(user_id, kind, ref):
            return
        subject, text, html = build(row)
        if mailer.send(row["email"], subject, text, html):
            sent += 1
        else:
            _release(kind, ref)

    pricing, account = f"{frontend_url()}/#/pricing", f"{frontend_url()}/#/account"
    for r in failed:
        _go(r["user_id"], "payment_failed", f"{r['id']}:{int(r['current_period_end'] or 0)}",
            lambda row, r=r: mailer.payment_failed_message(row["lang"], _name(row), plans.get_plan(r["plan"]).name, account))
    for r in ending:
        date = datetime.fromtimestamp(r["ends"], tz=timezone.utc).strftime("%Y-%m-%d")
        _go(r["user_id"], "plan_expiring", f"{r['user_id']}:{int(r['ends'])}",
            lambda row, r=r, d=date: mailer.plan_expiring_message(row["lang"], _name(row), plans.get_plan(r["plan"]).name, d, pricing))
    for r in ended:
        _go(r["user_id"], "plan_ended", f"{r['user_id']}:{int(r['ends'])}",
            lambda row, r=r: mailer.plan_ended_message(row["lang"], _name(row), plans.get_plan(r["plan"]).name, pricing))
    return sent


# ---- low credits ----------------------------------------------------------------------------
def check_low_credits(user_id: int) -> bool:
    """One 'running low' email per user per month, when what is left falls to 10% of what
    they had (at least 5). Called after a charge is settled."""
    if not (plans.paid_mode() and mailer.enabled()):
        return False
    bal = credits.balance(user_id)
    total = bal["plan_total"] + bal["topup_remaining"]
    if total <= 0 or bal["remaining"] > max(5, int(total * 0.1)):
        return False
    month = datetime.fromtimestamp(db.now(), tz=timezone.utc).strftime("%Y-%m")
    ref = f"{user_id}:{month}"
    if not _claim(user_id, "low_credit", ref):
        return False
    row = _user_row(user_id)
    if row is None:
        return False
    subject, text, html = mailer.low_credit_message(row["lang"], _name(row), bal["remaining"],
                                                    f"{frontend_url()}/#/pricing")
    if mailer.send(row["email"], subject, text, html):
        return True
    _release("low_credit", ref)
    return False
