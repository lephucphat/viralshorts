"""SQLite access: one short-lived connection per operation.

Per-call connections keep this safe under FastAPI's thread pool (sqlite3
connections must not be shared across threads) and WAL mode lets readers and
the single writer overlap. The path comes from ``STUDIO_DB_PATH`` and defaults
to ``data/studio.db`` next to the app, deliberately outside ``output/`` so the
job sweeps can never delete the accounts.
"""

import contextlib
import os
import sqlite3
import threading
import time

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_init_lock = threading.Lock()
_initialised_for = None


def db_path() -> str:
    return os.environ.get("STUDIO_DB_PATH") or os.path.join(_BASE, "data", "studio.db")


def data_dir() -> str:
    """Directory that holds the database and the files that belong to it."""
    return os.path.dirname(db_path()) or "."


# Each entry upgrades the schema by one version. Never edit a shipped entry:
# append a new one.
MIGRATIONS = [
    """
    CREATE TABLE users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
        name          TEXT NOT NULL DEFAULT '',
        password_hash TEXT NOT NULL,
        plan          TEXT NOT NULL DEFAULT 'free',
        lang          TEXT NOT NULL DEFAULT 'vi',
        token_version INTEGER NOT NULL DEFAULT 0,
        created_at    REAL NOT NULL,
        last_login_at REAL
    );

    CREATE TABLE projects (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id           TEXT NOT NULL UNIQUE,
        user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title            TEXT NOT NULL DEFAULT '',
        source_kind      TEXT NOT NULL DEFAULT 'file',
        source_ref       TEXT NOT NULL DEFAULT '',
        status           TEXT NOT NULL DEFAULT 'queued',
        duration_seconds REAL NOT NULL DEFAULT 0,
        clip_count       INTEGER NOT NULL DEFAULT 0,
        top_score        INTEGER,
        cover_url        TEXT,
        options          TEXT NOT NULL DEFAULT '{}',
        minutes_charged  INTEGER NOT NULL DEFAULT 0,
        created_at       REAL NOT NULL,
        updated_at       REAL NOT NULL,
        finished_at      REAL
    );
    CREATE INDEX idx_projects_user ON projects(user_id, created_at DESC);

    CREATE TABLE brand_kits (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name            TEXT NOT NULL,
        logo_path       TEXT,
        logo_position   TEXT NOT NULL DEFAULT 'top-right',
        logo_opacity    REAL NOT NULL DEFAULT 0.9,
        logo_scale      REAL NOT NULL DEFAULT 0.14,
        primary_color   TEXT NOT NULL DEFAULT '#111111',
        secondary_color TEXT NOT NULL DEFAULT '#FFFFFF',
        caption_preset  TEXT NOT NULL DEFAULT 'tiktok',
        hook_style      TEXT NOT NULL DEFAULT 'classic',
        layout          TEXT NOT NULL DEFAULT 'auto',
        output_format   TEXT NOT NULL DEFAULT 'vertical',
        is_default      INTEGER NOT NULL DEFAULT 0,
        created_at      REAL NOT NULL,
        updated_at      REAL NOT NULL
    );
    CREATE INDEX idx_brand_user ON brand_kits(user_id);

    CREATE TABLE usage_ledger (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        job_id     TEXT,
        minutes    INTEGER NOT NULL,
        kind       TEXT NOT NULL DEFAULT 'process',
        created_at REAL NOT NULL
    );
    CREATE UNIQUE INDEX idx_usage_job ON usage_ledger(job_id, kind) WHERE job_id IS NOT NULL;
    CREATE INDEX idx_usage_user ON usage_ledger(user_id, created_at);
    """,
    # 2: Google sign-in. An account made through Google has no password
    # (password_hash = ''), which verify_password never accepts.
    """
    ALTER TABLE users ADD COLUMN google_sub TEXT;
    ALTER TABLE users ADD COLUMN avatar_url TEXT;
    CREATE UNIQUE INDEX idx_users_google ON users(google_sub) WHERE google_sub IS NOT NULL;
    """,
    # 3: paid edition (plans.py). Credits live in grants (what a user was given and
    # what is left of it) and a ledger of what was spent; an allocation row says
    # which grant paid for which spend so a refund goes back where it came from.
    # payment_events is the webhook idempotency table: a provider retries events,
    # and the same event must never grant credits twice.
    """
    ALTER TABLE users ADD COLUMN payment_customer_id TEXT;

    CREATE TABLE subscriptions (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id              INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        provider             TEXT NOT NULL,
        provider_ref         TEXT NOT NULL,
        plan                 TEXT NOT NULL,
        status               TEXT NOT NULL,
        current_period_start REAL,
        current_period_end   REAL,
        cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
        created_at           REAL NOT NULL,
        updated_at           REAL NOT NULL
    );
    CREATE UNIQUE INDEX idx_sub_ref ON subscriptions(provider, provider_ref);
    CREATE INDEX idx_sub_user ON subscriptions(user_id, status);

    CREATE TABLE credit_grants (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        kind       TEXT NOT NULL,
        amount     INTEGER NOT NULL,
        remaining  INTEGER NOT NULL,
        expires_at REAL,
        source_ref TEXT,
        created_at REAL NOT NULL
    );
    CREATE UNIQUE INDEX idx_grants_ref ON credit_grants(source_ref) WHERE source_ref IS NOT NULL;
    CREATE INDEX idx_grants_user ON credit_grants(user_id, remaining);

    CREATE TABLE credit_ledger (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        ref        TEXT NOT NULL,
        kind       TEXT NOT NULL,
        credits    INTEGER NOT NULL,
        status     TEXT NOT NULL,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    );
    CREATE UNIQUE INDEX idx_ledger_ref ON credit_ledger(ref, kind);
    CREATE INDEX idx_ledger_user ON credit_ledger(user_id, created_at);
    CREATE INDEX idx_ledger_day ON credit_ledger(created_at, status);

    CREATE TABLE credit_allocations (
        ledger_id INTEGER NOT NULL REFERENCES credit_ledger(id) ON DELETE CASCADE,
        grant_id  INTEGER NOT NULL REFERENCES credit_grants(id) ON DELETE CASCADE,
        amount    INTEGER NOT NULL
    );
    CREATE INDEX idx_alloc_ledger ON credit_allocations(ledger_id);

    CREATE TABLE payments (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        provider     TEXT NOT NULL,
        provider_ref TEXT NOT NULL,
        kind         TEXT NOT NULL,
        item         TEXT NOT NULL,
        amount       INTEGER NOT NULL,
        currency     TEXT NOT NULL,
        credits      INTEGER NOT NULL DEFAULT 0,
        status       TEXT NOT NULL,
        created_at   REAL NOT NULL,
        paid_at      REAL
    );
    CREATE UNIQUE INDEX idx_pay_ref ON payments(provider, provider_ref);
    CREATE INDEX idx_pay_user ON payments(user_id, created_at DESC);

    CREATE TABLE payment_events (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        provider   TEXT NOT NULL,
        event_id   TEXT NOT NULL,
        type       TEXT NOT NULL,
        created_at REAL NOT NULL
    );
    CREATE UNIQUE INDEX idx_event_id ON payment_events(provider, event_id)
    """,
    # 4: account lifecycle and the admin console. email_verified_at proves the inbox
    # (Google already did); disabled_at locks an account without deleting it.
    # auth_tokens holds only the sha256 of the emailed token. notifications makes
    # every email idempotent: one (kind, ref) row is one email, however often the
    # code that sends it runs. admin_audit records what an admin did to whom.
    """
    ALTER TABLE users ADD COLUMN email_verified_at REAL;
    ALTER TABLE users ADD COLUMN disabled_at REAL;
    UPDATE users SET email_verified_at = created_at WHERE google_sub IS NOT NULL;

    CREATE TABLE auth_tokens (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        kind       TEXT NOT NULL,
        token_hash TEXT NOT NULL,
        expires_at REAL NOT NULL,
        used_at    REAL,
        created_at REAL NOT NULL
    );
    CREATE UNIQUE INDEX idx_auth_token_hash ON auth_tokens(token_hash);
    CREATE INDEX idx_auth_token_user ON auth_tokens(user_id, kind);

    CREATE TABLE notifications (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        kind       TEXT NOT NULL,
        ref        TEXT NOT NULL,
        created_at REAL NOT NULL
    );
    CREATE UNIQUE INDEX idx_notify_ref ON notifications(kind, ref);

    CREATE TABLE admin_audit (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id   INTEGER NOT NULL,
        action     TEXT NOT NULL,
        user_id    INTEGER,
        detail     TEXT NOT NULL DEFAULT '{}',
        created_at REAL NOT NULL
    );
    CREATE INDEX idx_audit_time ON admin_audit(created_at DESC)
    """,
    # 5: the durable clip library (archive.py). The row says whether a project's files
    # are in object storage, how big they are and when the plan's retention ends.
    # archived_at is set when the upload finished and cleared when the objects are purged;
    # archive_expires_at survives the purge so the UI can say "expired" rather than "never".
    """
    ALTER TABLE projects ADD COLUMN archived_at REAL;
    ALTER TABLE projects ADD COLUMN archive_bytes INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE projects ADD COLUMN archive_expires_at REAL;
    CREATE INDEX idx_projects_archive ON projects(archive_expires_at) WHERE archived_at IS NOT NULL
    """,
    # 6: hardening. rate_hits makes the login / reset throttles survive a restart or a
    # deploy. payment_records keeps what an accounting audit needs after an account is
    # deleted (payments cascade away with the user, this copy does not). payments.provider_aux
    # holds the provider's payment-intent / charge id so a refund or dispute webhook can find
    # the payment. email_canonical folds Gmail dots and +tags so one inbox cannot farm the
    # free credits with aliases. tos_* records which terms the person accepted and when.
    """
    CREATE TABLE rate_hits (
        bucket TEXT NOT NULL,
        at     REAL NOT NULL
    );
    CREATE INDEX idx_rate_bucket ON rate_hits(bucket, at);

    CREATE TABLE payment_records (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER NOT NULL,
        provider     TEXT NOT NULL,
        provider_ref TEXT NOT NULL,
        kind         TEXT NOT NULL,
        item         TEXT NOT NULL,
        amount       INTEGER NOT NULL,
        currency     TEXT NOT NULL,
        status       TEXT NOT NULL,
        paid_at      REAL,
        deleted_at   REAL NOT NULL
    );
    CREATE INDEX idx_records_time ON payment_records(paid_at);

    ALTER TABLE payments ADD COLUMN provider_aux TEXT;
    CREATE INDEX idx_pay_aux ON payments(provider, provider_aux) WHERE provider_aux IS NOT NULL;

    ALTER TABLE users ADD COLUMN email_canonical TEXT;
    CREATE INDEX idx_users_canonical ON users(email_canonical);

    ALTER TABLE users ADD COLUMN tos_accepted_at REAL;
    ALTER TABLE users ADD COLUMN tos_version TEXT
    """,
    # 7: API keys for the programmatic API and the MCP endpoint (only the sha256 of a key is
    # stored, the key itself is shown once), and a payload on emailed tokens so an
    # email-change link can carry the new address.
    """
    CREATE TABLE api_keys (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name         TEXT NOT NULL DEFAULT '',
        prefix       TEXT NOT NULL,
        key_hash     TEXT NOT NULL,
        created_at   REAL NOT NULL,
        last_used_at REAL,
        revoked_at   REAL
    );
    CREATE UNIQUE INDEX idx_api_key_hash ON api_keys(key_hash);
    CREATE INDEX idx_api_key_user ON api_keys(user_id);

    ALTER TABLE auth_tokens ADD COLUMN payload TEXT
    """,
    # 8: money side. cost_usd is the ESTIMATED provider cost of a settled ledger row (rates in
    # plans.py), so the admin console can show margin. billing_info is what a customer wants
    # on an invoice; invoice_requested_at marks a payment they asked an invoice for. promo codes
    # hand out credits (one redemption per person per code).
    """
    ALTER TABLE credit_ledger ADD COLUMN cost_usd REAL NOT NULL DEFAULT 0;

    CREATE TABLE billing_info (
        user_id    INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        company    TEXT NOT NULL DEFAULT '',
        tax_code   TEXT NOT NULL DEFAULT '',
        address    TEXT NOT NULL DEFAULT '',
        email      TEXT NOT NULL DEFAULT '',
        updated_at REAL NOT NULL
    );

    ALTER TABLE payments ADD COLUMN invoice_requested_at REAL;

    CREATE TABLE promo_codes (
        code       TEXT PRIMARY KEY COLLATE NOCASE,
        credits    INTEGER NOT NULL,
        max_uses   INTEGER NOT NULL DEFAULT 0,
        used       INTEGER NOT NULL DEFAULT 0,
        expires_at REAL,
        active     INTEGER NOT NULL DEFAULT 1,
        note       TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL
    );

    CREATE TABLE promo_redemptions (
        code        TEXT NOT NULL COLLATE NOCASE,
        user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        credits     INTEGER NOT NULL,
        redeemed_at REAL NOT NULL,
        PRIMARY KEY (code, user_id)
    )
    """,
    # 9: onboarding checklist. Most steps are derived from data that already exists (verified
    # email, a brand kit, a project); only what the server cannot see is stored here: the
    # pricing page was opened, a social network was connected (the key lives in the browser),
    # and the person closed the checklist. One row per user, created on first write.
    """
    CREATE TABLE onboarding (
        user_id             INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        pricing_seen_at     REAL,
        social_connected_at REAL,
        dismissed_at        REAL,
        updated_at          REAL NOT NULL
    )
    """,
    # 10: the posting calendar and friend referrals. scheduled_posts is the calendar's own record
    # (what was planned, for when, and how far it got); the real queue lives at Upload-Post under
    # the person's own key, vendor_job_id links the two. scheduled_for is a UTC epoch, timezone the
    # IANA zone the person planned it in. referrals links a new account to the account whose code
    # it used; it stays 'pending' until the new account pays for the first time.
    """
    CREATE TABLE scheduled_posts (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        job_id        TEXT NOT NULL,
        clip_index    INTEGER NOT NULL DEFAULT 0,
        title         TEXT NOT NULL DEFAULT '',
        description   TEXT NOT NULL DEFAULT '',
        platforms     TEXT NOT NULL DEFAULT '[]',
        scheduled_for REAL NOT NULL,
        timezone      TEXT NOT NULL DEFAULT 'UTC',
        status        TEXT NOT NULL DEFAULT 'planned',
        vendor_job_id TEXT,
        error         TEXT NOT NULL DEFAULT '',
        created_at    REAL NOT NULL,
        updated_at    REAL NOT NULL
    );
    CREATE INDEX idx_sched_user_time ON scheduled_posts(user_id, scheduled_for);
    CREATE INDEX idx_sched_vendor ON scheduled_posts(user_id, vendor_job_id) WHERE vendor_job_id IS NOT NULL;

    CREATE TABLE referrals (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        referee_id     INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        code           TEXT NOT NULL COLLATE NOCASE,
        status         TEXT NOT NULL DEFAULT 'pending',
        reward_credits INTEGER NOT NULL DEFAULT 0,
        created_at     REAL NOT NULL,
        rewarded_at    REAL
    );
    CREATE INDEX idx_referrals_referrer ON referrals(referrer_id, status)
    """,
    # 11: the project library grows folders. favorite is a plain flag on the project; a collection
    # is a named folder that holds projects (a project can sit in several). Deleting a project or a
    # collection removes only the link, never the other side.
    """
    ALTER TABLE projects ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0;

    CREATE TABLE collections (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name       TEXT NOT NULL,
        created_at REAL NOT NULL,
        UNIQUE (user_id, name COLLATE NOCASE)
    );

    CREATE TABLE collection_projects (
        collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
        project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        added_at      REAL NOT NULL,
        PRIMARY KEY (collection_id, project_id)
    );
    CREATE INDEX idx_collection_projects_project ON collection_projects(project_id)
    """,
    # 12: recipes are saved sets of create-project settings (genre, length, layout and so on) that
    # a person re-applies with one click. settings is a JSON object that studio/recipes.py filters
    # to a known list of keys, so nothing arbitrary is stored.
    """
    CREATE TABLE recipes (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name       TEXT NOT NULL,
        settings   TEXT NOT NULL,
        created_at REAL NOT NULL,
        UNIQUE (user_id, name COLLATE NOCASE)
    )
    """,
    # 13: the in-app bell. Rows carry a kind, a reference and a little JSON data, never prose.
    # The older notifications table is a different thing: it only de-duplicates emails.
    """
    CREATE TABLE inbox (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        kind       TEXT NOT NULL,
        ref        TEXT NOT NULL,
        data       TEXT NOT NULL DEFAULT '{}',
        read_at    REAL,
        created_at REAL NOT NULL,
        UNIQUE (user_id, kind, ref)
    );
    CREATE INDEX idx_inbox_user ON inbox(user_id, id)
    """,
    # 14: what the standalone tools produced (thumbnails today), so it is still there after the
    # person leaves the page. The file lives under output/; this table is the index of whose it is.
    """
    CREATE TABLE tool_assets (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        kind       TEXT NOT NULL,
        url        TEXT NOT NULL,
        title      TEXT NOT NULL DEFAULT '',
        text       TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL,
        UNIQUE (user_id, url)
    );
    CREATE INDEX idx_tool_assets_user ON tool_assets(user_id, kind, id)
    """,
    # 15: unfinished work in a tool, listed under it like a draft project. id is made by the browser
    # (unique per person); data is the tool's own state as JSON, filtered by studio/drafts.py.
    """
    CREATE TABLE tool_drafts (
        user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        id         TEXT NOT NULL,
        kind       TEXT NOT NULL,
        title      TEXT NOT NULL DEFAULT '',
        step       INTEGER NOT NULL DEFAULT 0,
        preview    TEXT NOT NULL DEFAULT '',
        data       TEXT NOT NULL,
        updated_at REAL NOT NULL,
        PRIMARY KEY (user_id, id)
    );
    CREATE INDEX idx_tool_drafts_user ON tool_drafts(user_id, kind, updated_at)
    """,
]


def _connect() -> sqlite3.Connection:
    path = db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def init() -> None:
    """Create or upgrade the schema. Idempotent and cheap after the first call."""
    global _initialised_for
    path = db_path()
    if _initialised_for == path and os.path.exists(path):
        return
    with _init_lock:
        conn = _connect()
        try:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            for target, script in enumerate(MIGRATIONS, start=1):
                if version >= target:
                    continue
                conn.execute("BEGIN IMMEDIATE")
                try:
                    for statement in _split(script):
                        conn.execute(statement)
                    conn.execute(f"PRAGMA user_version = {target}")
                    conn.execute("COMMIT")
                except Exception:
                    conn.execute("ROLLBACK")
                    raise
            _backfill_canonical(conn)
        finally:
            conn.close()
        _initialised_for = path


def _backfill_canonical(conn) -> None:
    """Fill email_canonical for accounts that predate migration 6 (SQL cannot fold dots)."""
    from . import emailnorm
    rows = conn.execute("SELECT id, email FROM users WHERE email_canonical IS NULL").fetchall()
    if not rows:
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        for r in rows:
            conn.execute("UPDATE users SET email_canonical = ? WHERE id = ?",
                         (emailnorm.canonical(r["email"]), r["id"]))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def _split(script: str):
    return [s.strip() for s in script.split(";") if s.strip()]


@contextlib.contextmanager
def connection():
    """A connection inside one transaction: committed on success, rolled back on error."""
    init()
    conn = _connect()
    try:
        conn.execute("BEGIN")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        conn.close()


@contextlib.contextmanager
def write_connection():
    """Like ``connection`` but takes the write lock up front (BEGIN IMMEDIATE).

    Use it for read-then-write sequences such as spending credits: with a plain
    deferred BEGIN, two requests can both read the same balance and then fail
    or overspend when the second tries to upgrade to a writer.
    """
    init()
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        conn.close()


def now() -> float:
    return time.time()
