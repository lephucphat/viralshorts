"""Accounts: registration, login, profile, and request -> user."""

import os
import re
import time
from dataclasses import dataclass
from typing import Optional

from . import db, emailnorm, security


class AuthError(Exception):
    """A user-facing failure. ``code`` is stable for the client, ``status`` is HTTP."""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass
class User:
    id: int
    email: str
    name: str
    plan: str
    lang: str
    token_version: int
    created_at: float
    has_password: bool = True
    has_google: bool = False
    avatar_url: Optional[str] = None
    email_verified: bool = False
    disabled: bool = False

    @property
    def is_admin(self) -> bool:
        """Admin = listed in ADMIN_EMAILS **and** the inbox is proven. Without the
        second half, whoever registered an admin's address first would be admin."""
        return self.email_verified and not self.disabled and self.email.lower() in admin_emails()

    def public(self) -> dict:
        return {"id": self.id, "email": self.email, "name": self.name,
                "plan": self.plan, "lang": self.lang, "created_at": self.created_at,
                "has_password": self.has_password, "has_google": self.has_google,
                "avatar_url": self.avatar_url, "email_verified": self.email_verified,
                "is_admin": self.is_admin}


def admin_emails() -> set:
    raw = os.environ.get("ADMIN_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
SUPPORTED_LANGS = ("vi", "en")


def _row(row) -> Optional[User]:
    if row is None:
        return None
    return User(id=row["id"], email=row["email"], name=row["name"], plan=row["plan"],
                lang=row["lang"], token_version=row["token_version"],
                created_at=row["created_at"], has_password=bool(row["password_hash"]),
                has_google=bool(row["google_sub"]), avatar_url=row["avatar_url"],
                email_verified=row["email_verified_at"] is not None,
                disabled=row["disabled_at"] is not None)


# --- throttling ------------------------------------------------------------
# Kept in SQLite (rate_hits) so a restart or a deploy does not hand a password guesser a
# fresh allowance. It stops guessing and registration floods; it is not an audit log.
def throttle(bucket: str, limit: int, window_seconds: int) -> None:
    """Raise 429 once ``bucket`` has been hit ``limit`` times within the window."""
    now = time.time()
    with db.write_connection() as conn:
        conn.execute("DELETE FROM rate_hits WHERE bucket = ? AND at <= ?", (bucket, now - window_seconds))
        used = conn.execute("SELECT COUNT(*) FROM rate_hits WHERE bucket = ?", (bucket,)).fetchone()[0]
        if used >= limit:
            raise AuthError("too_many_attempts",
                            "Too many attempts. Please wait a few minutes and try again.", 429)
        conn.execute("INSERT INTO rate_hits (bucket, at) VALUES (?, ?)", (bucket, now))


def reset_throttle(bucket: str) -> None:
    with db.connection() as conn:
        conn.execute("DELETE FROM rate_hits WHERE bucket = ?", (bucket,))


def clear_all_throttles() -> None:
    with db.connection() as conn:
        conn.execute("DELETE FROM rate_hits")


def purge_old_throttles(max_age_seconds: int = 86400) -> int:
    """Housekeeping for the cleanup loop: drop hits no window can still count."""
    with db.connection() as conn:
        return conn.execute("DELETE FROM rate_hits WHERE at <= ?", (time.time() - max_age_seconds,)).rowcount


# --- validation --------------------------------------------------------------
def normalise_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not _EMAIL_RE.match(email) or len(email) > 254:
        raise AuthError("invalid_email", "Enter a valid email address.", 422)
    return email


# The passwords guessed first in every credential-stuffing run. Not a full dictionary: it only
# has to stop the ones that fall in seconds. Compared lower-case.
_COMMON_PASSWORDS = frozenset("""
12345678 123456789 1234567890 11111111 00000000 87654321 password password1 password123 passw0rd
qwerty123 qwertyuiop iloveyou admin123 welcome1 welcome123 letmein1 abc12345 abcd1234 1q2w3e4r
1qaz2wsx zaq12wsx monkey123 dragon123 football1 baseball1 superman1 trustno1 changeme sunshine1
princess1 whatever1 starwars1 matkhau123 matkhau1234 anhyeuem123 123123123 111222333 12341234
""".split())


def check_password(password: str) -> None:
    if not isinstance(password, str) or len(password) < security.MIN_PASSWORD:
        raise AuthError("weak_password",
                        f"Password must be at least {security.MIN_PASSWORD} characters.", 422)
    if len(password) > security.MAX_PASSWORD:
        raise AuthError("password_too_long",
                        f"Password must be at most {security.MAX_PASSWORD} characters.", 422)
    if password.lower() in _COMMON_PASSWORDS or len(set(password)) == 1:
        raise AuthError("common_password", "That password is too common. Choose another.", 422)


# --- operations ----------------------------------------------------------------
def register(email: str, password: str, name: str = "", lang: str = "vi",
             client_ip: str = "", tos_version: str = "") -> User:
    if client_ip:
        throttle(f"register:{client_ip}", 10, 3600)
    email = normalise_email(email)
    check_password(password)
    if emailnorm.is_disposable(email):
        raise AuthError("disposable_email", "Please use a permanent email address.", 422)
    name = (name or "").strip()[:80] or email.split("@")[0]
    lang = lang if lang in SUPPORTED_LANGS else "vi"
    pw_hash = security.hash_password(password)
    canon = emailnorm.canonical(email)
    with db.write_connection() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email = ? OR email_canonical = ?",
                        (email, canon)).fetchone():
            raise AuthError("email_taken", "An account with this email already exists.", 409)
        cur = conn.execute(
            "INSERT INTO users (email, email_canonical, name, password_hash, lang, created_at, "
            "tos_accepted_at, tos_version) VALUES (?,?,?,?,?,?,?,?)",
            (email, canon, name, pw_hash, lang, db.now(),
             db.now() if tos_version else None, tos_version or None))
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _row(row)


def login(email: str, password: str, client_ip: str = "") -> User:
    email_key = (email or "").strip().lower()
    throttle(f"login:{client_ip}:{email_key}", 8, 600)
    # A second bucket on the address alone: many IPs guessing at one account still stop.
    throttle(f"login-email:{email_key}", 30, 3600)
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email_key,)).fetchone()
        stored = row["password_hash"] if row else security.DUMMY_HASH
        ok = security.verify_password(password or "", stored)
        if not row or not ok:
            raise AuthError("bad_credentials", "Incorrect email or password.", 401)
        if row["disabled_at"] is not None:
            raise AuthError("account_disabled", "This account has been disabled. Contact support.", 403)
        conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (db.now(), row["id"]))
    reset_throttle(f"login:{client_ip}:{email_key}")
    reset_throttle(f"login-email:{email_key}")
    return _row(row)


def get(user_id: int) -> Optional[User]:
    with db.connection() as conn:
        return _row(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


def issue_token(user: User) -> str:
    return security.create_token(user.id, user.token_version)


def user_from_token(token: str) -> Optional[User]:
    data = security.verify_token(token or "")
    if not data:
        return None
    try:
        user = get(int(data["sub"]))
    except (KeyError, ValueError):
        return None
    if user is None or user.disabled or user.token_version != int(data.get("tv", -1)):
        return None
    return user


def user_from_request(request) -> Optional[User]:
    """The signed-in user for a Starlette request, or None. Never raises."""
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
        if token.startswith("vsk_"):                 # an API key, not a session token
            from . import apikeys
            return apikeys.user_for_key(token)
        return user_from_token(token)
    return None


def terms_version() -> str:
    """Which edition of the terms a new account accepts (bump TERMS_VERSION when they change)."""
    return os.environ.get("TERMS_VERSION", "2026-11").strip() or "2026-11"


def terms_required() -> bool:
    """Sign-up must carry an explicit acceptance of the terms. On by default in production
    (``APP_ENV=production``); ``REQUIRE_TERMS=0/1`` overrides."""
    raw = os.environ.get("REQUIRE_TERMS", "").strip().lower()
    if raw:
        return raw in ("1", "true", "yes")
    return security.production()


def logout_everywhere(user_id: int) -> User:
    """Revoke every session and token of the account (the caller gets a fresh one)."""
    with db.connection() as conn:
        conn.execute("UPDATE users SET token_version = token_version + 1 WHERE id = ?", (user_id,))
    return get(user_id)


def update_profile(user_id: int, name: Optional[str] = None, lang: Optional[str] = None) -> User:
    fields, values = [], []
    if name is not None:
        fields.append("name = ?")
        values.append(name.strip()[:80])
    if lang is not None:
        if lang not in SUPPORTED_LANGS:
            raise AuthError("invalid_lang", "Unsupported language.", 422)
        fields.append("lang = ?")
        values.append(lang)
    if fields:
        with db.connection() as conn:
            conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", (*values, user_id))
    return get(user_id)


def change_password(user_id: int, current: str, new: str) -> User:
    check_password(new)
    # A stolen session token must not be able to guess the current password at full speed.
    throttle(f"pwcheck:{user_id}", 8, 600)
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise AuthError("bad_credentials", "Current password is incorrect.", 401)
        # A Google-only account has no password yet: being signed in is proof
        # enough to set the first one. Otherwise the current password is required.
        if row["password_hash"] and not security.verify_password(current or "", row["password_hash"]):
            raise AuthError("bad_credentials", "Current password is incorrect.", 401)
        # Bumping token_version invalidates every token issued before now.
        conn.execute("UPDATE users SET password_hash = ?, token_version = token_version + 1 "
                     "WHERE id = ?", (security.hash_password(new), user_id))
    reset_throttle(f"pwcheck:{user_id}")
    return get(user_id)


def confirm_identity(user_id: int, password: str) -> dict:
    """Check the password (or, for a Google-only account, the typed email) before a
    destructive step. Returns the account's email and language. Shares one throttle with
    ``change_password``."""
    throttle(f"pwcheck:{user_id}", 8, 600)
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise AuthError("bad_credentials", "Password is incorrect.", 401)
    if row["password_hash"]:
        confirmed = security.verify_password(password or "", row["password_hash"])
    else:
        # No password to retype: confirm by typing the account's email.
        confirmed = (password or "").strip().lower() == row["email"].lower()
    if not confirmed:
        raise AuthError("bad_credentials", "Password is incorrect.", 401)
    reset_throttle(f"pwcheck:{user_id}")
    return {"email": row["email"], "name": row["name"], "lang": row["lang"]}


def delete_account(user_id: int, password: str) -> dict:
    """Delete the account and everything that cascades from it.

    The ``payments`` rows cascade away with the user, but a shop has to keep proof of what
    it was paid, so every settled payment is copied into ``payment_records`` (no link to the
    person any more) in the same transaction. The caller has already cancelled any recurring
    subscription at the provider: deleting the row would not stop the card being charged."""
    who = confirm_identity(user_id, password)
    erase_account(user_id)
    return who


_ERASE_HOOKS: list = []


def register_erase_hook(fn) -> None:
    """``fn(user_id)`` runs just before the account rows go, to remove files the database
    only points at (clips, thumbnails). It runs first because afterwards nothing says whose
    they were. A failing hook is logged and does not stop the erasure."""
    if fn not in _ERASE_HOOKS:
        _ERASE_HOOKS.append(fn)


def erase_account(user_id: int) -> None:
    """The deletion itself, without asking for a password (the owner's own request goes
    through ``delete_account``; an administrator's goes straight here)."""
    for hook in list(_ERASE_HOOKS):
        try:
            hook(user_id)
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ erase hook failed for user {user_id}: {e}")
    with db.write_connection() as conn:
        conn.execute(
            "INSERT INTO payment_records (user_id, provider, provider_ref, kind, item, amount, currency, "
            "status, paid_at, deleted_at) SELECT user_id, provider, provider_ref, kind, item, amount, "
            "currency, status, paid_at, ? FROM payments WHERE user_id = ? AND status IN ('paid','refunded')",
            (db.now(), user_id))
        # The person's own referral code is a promo code, not a row that cascades.
        conn.execute("DELETE FROM promo_codes WHERE note = ?", (f"referral:{int(user_id)}",))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))  # cascades


def login_with_google(sub: str, email: str, name: str = "", picture: str = "",
                      locale: str = "") -> User:
    """Find or create the account for a Google identity. ``email`` must already be
    verified by Google (the caller checks ``email_verified``).

    Match order: the Google subject (stable even if the email changes), then the
    email, which links Google to an existing password account of the same inbox.
    """
    email = normalise_email(email)
    lang = "en" if (locale or "").lower().startswith("en") else "vi"
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE google_sub = ?", (sub,)).fetchone()
        if row is None:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if row is not None and row["disabled_at"] is None:
                conn.execute("UPDATE users SET google_sub = ?, avatar_url = COALESCE(avatar_url, ?) "
                             "WHERE id = ?", (sub, picture or None, row["id"]))
                if row["email_verified_at"] is None:
                    # Pre-hijacking: someone may have registered this address with a password
                    # they chose before its owner ever signed in. The owner has now proven the
                    # inbox, so whatever password and sessions exist were not theirs.
                    conn.execute("UPDATE users SET password_hash = '', token_version = token_version + 1 "
                                 "WHERE id = ?", (row["id"],))
        if row is None:
            cur = conn.execute(
                "INSERT INTO users (email, email_canonical, name, password_hash, lang, created_at, "
                "google_sub, avatar_url, email_verified_at, tos_accepted_at, tos_version) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (email, emailnorm.canonical(email), (name or "").strip()[:80] or email.split("@")[0], "",
                 lang, db.now(), sub, picture or None, db.now(), db.now(), terms_version()))
            row_id = cur.lastrowid
        else:
            row_id = row["id"]
            if row["disabled_at"] is not None:
                raise AuthError("account_disabled", "This account has been disabled.", 403)
        # Google verified the address, so the inbox is proven whichever way we got here.
        conn.execute("UPDATE users SET last_login_at = ?, email_verified_at = COALESCE(email_verified_at, ?) "
                     "WHERE id = ?", (db.now(), db.now(), row_id))
        row = conn.execute("SELECT * FROM users WHERE id = ?", (row_id,)).fetchone()
    return _row(row)
