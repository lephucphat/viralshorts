"""The credit wallet: grants, reservations, charges and refunds.

A user's balance is the sum of ``credit_grants.remaining`` over grants that have
not expired. Spending is a three-step protocol so that an expensive operation
cannot be paid for by nobody:

    reserve(user, ref, kind, credits)   take the credits now (fails with QuotaError)
    commit(ledger_id, actual=None)      the work succeeded; optionally true-up the amount
    release(ledger_id)                  the work failed; give everything back

Credits are taken from the grants that expire soonest first (the monthly plan
credits), and only then from the ones that never expire (top-ups). Every spend
records which grant paid for it (``credit_allocations``) so a refund returns the
credits to the grant they came from.

All writes run under ``BEGIN IMMEDIATE`` (``db.write_connection``): two
concurrent requests cannot read the same balance and both spend it.
"""

from datetime import datetime, timezone
from typing import Optional

from . import db, plans

RESERVED = "reserved"
COMMITTED = "committed"
RELEASED = "released"

_NEVER = 4102444800.0  # 2100-01-01, sorts non-expiring grants last


class QuotaError(Exception):
    def __init__(self, remaining: int, required: int = 0):
        super().__init__("Not enough credits.")
        self.remaining = remaining
        self.required = required


class BudgetError(Exception):
    """The site-wide daily spending ceiling was reached."""


def is_unlimited(user_id: int) -> bool:
    """Operators (verified ``ADMIN_EMAILS``) are not metered: they run the service and
    test every feature. Their work is still written to the ledger, so cost reports
    stay honest, but nothing is taken from grants and no balance check applies.
    ``ADMIN_UNLIMITED=0`` turns this off (to test the paywall as an admin)."""
    import os
    if os.environ.get("ADMIN_UNLIMITED", "1").strip().lower() in ("0", "false", "no", "off"):
        return False
    from .auth import admin_emails
    allowed = admin_emails()
    if not allowed:
        return False
    with db.connection() as conn:
        row = conn.execute(
            "SELECT email, email_verified_at, disabled_at FROM users WHERE id = ?",
            (user_id,)).fetchone()
    return (row is not None and row["email_verified_at"] is not None
            and row["disabled_at"] is None and row["email"].lower() in allowed)


def _month_bounds(ts: Optional[float] = None):
    dt = datetime.fromtimestamp(ts if ts is not None else db.now(), tz=timezone.utc)
    start = datetime(dt.year, dt.month, 1, tzinfo=timezone.utc)
    nxt = datetime(dt.year + (dt.month == 12), 1 if dt.month == 12 else dt.month + 1, 1,
                   tzinfo=timezone.utc)
    return start.timestamp(), nxt.timestamp(), start.strftime("%Y-%m")


# ---- grants -----------------------------------------------------------------------------
def grant(user_id: int, kind: str, amount: int, expires_at: Optional[float] = None,
          source_ref: Optional[str] = None, conn=None) -> bool:
    """Give a user credits. Idempotent per ``source_ref``: False if already given."""
    amount = int(amount)
    if amount <= 0:
        return False

    def _do(c):
        cur = c.execute(
            "INSERT OR IGNORE INTO credit_grants "
            "(user_id, kind, amount, remaining, expires_at, source_ref, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (user_id, kind, amount, amount, expires_at, source_ref, db.now()))
        return cur.rowcount == 1

    if conn is not None:
        return _do(conn)
    with db.write_connection() as c:
        return _do(c)


def ensure_free_grant(user_id: int, conn=None) -> None:
    """Hand out this month's credits to a user who is not on a paid plan.

    Lazy and idempotent: the first time the account is looked at in a new month
    the grant appears (one row per user per month, enforced by ``source_ref``).
    Paid plans get theirs from the payment webhook instead.
    """
    def _do(c):
        row = c.execute("SELECT plan, email_verified_at FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None or row["plan"] != plans.DEFAULT_PLAN:
            return
        # Free credits are the thing worth farming with throwaway addresses, so when
        # mail can be delivered they wait for a proven inbox.
        from . import mailer
        if mailer.verification_required() and row["email_verified_at"] is None:
            return
        _, end, label = _month_bounds()
        grant(user_id, "plan", plans.get_plan(plans.DEFAULT_PLAN).credits,
              expires_at=end, source_ref=f"free:{user_id}:{label}", conn=c)

    if conn is not None:
        _do(conn)
    else:
        with db.write_connection() as c:
            _do(c)


def _live_grants(conn, user_id: int, now: float):
    return conn.execute(
        "SELECT id, kind, amount, remaining, expires_at FROM credit_grants "
        "WHERE user_id = ? AND remaining > 0 AND (expires_at IS NULL OR expires_at > ?) "
        "ORDER BY COALESCE(expires_at, ?) ASC, id ASC", (user_id, now, _NEVER)).fetchall()


def balance(user_id: int) -> dict:
    """What the account can spend now, split so the UI can explain it."""
    now = db.now()
    ensure_free_grant(user_id)
    with db.connection() as conn:
        rows = _live_grants(conn, user_id, now)
        plan_left = sum(r["remaining"] for r in rows if r["kind"] == "plan")
        topup_left = sum(r["remaining"] for r in rows if r["kind"] != "plan")
        plan_total = sum(r["amount"] for r in rows if r["kind"] == "plan")
        reserved = conn.execute(
            "SELECT COALESCE(SUM(credits),0) AS c FROM credit_ledger "
            "WHERE user_id = ? AND status = ?", (user_id, RESERVED)).fetchone()["c"]
        next_expiry = min((r["expires_at"] for r in rows
                           if r["kind"] == "plan" and r["expires_at"]), default=None)
    return {
        "remaining": plan_left + topup_left,
        "plan_remaining": plan_left,
        "plan_total": plan_total,
        "topup_remaining": topup_left,
        "reserved": int(reserved),
        "plan_expires_at": next_expiry,
    }


def used_this_month(user_id: int) -> int:
    start, _, _ = _month_bounds()
    with db.connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(credits),0) AS c FROM credit_ledger "
            "WHERE user_id = ? AND status IN (?,?) AND created_at >= ?",
            (user_id, RESERVED, COMMITTED, start)).fetchone()
    return int(row["c"])


# ---- spending ----------------------------------------------------------------------------
def spent_today() -> int:
    """Credits spent (or held) site-wide since 00:00 UTC; what the daily budget counts."""
    with db.connection() as conn:
        return _spent_today(conn)


def _spent_today(conn) -> int:
    day = datetime.fromtimestamp(db.now(), tz=timezone.utc)
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp()
    row = conn.execute(
        "SELECT COALESCE(SUM(credits),0) AS c FROM credit_ledger "
        "WHERE status IN (?,?) AND created_at >= ?", (RESERVED, COMMITTED, start)).fetchone()
    return int(row["c"])


def _take(conn, ledger_id: int, user_id: int, credits: int, now: float) -> int:
    """Move up to ``credits`` out of the user's grants. Returns how many it took."""
    need = credits
    for g in _live_grants(conn, user_id, now):
        if need <= 0:
            break
        part = min(need, g["remaining"])
        conn.execute("UPDATE credit_grants SET remaining = remaining - ? WHERE id = ?",
                     (part, g["id"]))
        conn.execute("INSERT INTO credit_allocations (ledger_id, grant_id, amount) VALUES (?,?,?)",
                     (ledger_id, g["id"], part))
        need -= part
    return credits - need


def _give_back(conn, ledger_id: int, credits: int) -> int:
    """Return up to ``credits`` of a spend to the grants that paid for it."""
    left = credits
    rows = conn.execute(
        "SELECT rowid AS rid, grant_id, amount FROM credit_allocations "
        "WHERE ledger_id = ? AND amount > 0 ORDER BY rowid DESC", (ledger_id,)).fetchall()
    for r in rows:
        if left <= 0:
            break
        part = min(left, r["amount"])
        conn.execute("UPDATE credit_grants SET remaining = remaining + ? WHERE id = ?",
                     (part, r["grant_id"]))
        conn.execute("UPDATE credit_allocations SET amount = amount - ? WHERE rowid = ?",
                     (part, r["rid"]))
        left -= part
    return credits - left


def reserve(user_id: int, ref: str, kind: str, credits: int, budgeted: bool = False) -> int:
    """Take ``credits`` now. Returns the ledger id.

    Idempotent on ``(ref, kind)``: asking again for the same piece of work
    returns the existing entry instead of charging twice. ``budgeted`` marks
    spend that calls paid third-party APIs, which also counts against the
    site-wide daily ceiling.
    """
    credits = int(credits)
    if credits <= 0:
        raise ValueError("credits must be positive")
    now = db.now()
    ensure_free_grant(user_id)
    unlimited = is_unlimited(user_id)
    with db.write_connection() as conn:
        existing = conn.execute(
            "SELECT id, status FROM credit_ledger WHERE ref = ? AND kind = ?",
            (ref, kind)).fetchone()
        if existing is not None and existing["status"] != RELEASED:
            return int(existing["id"])
        if budgeted and not unlimited:
            ceiling = plans.daily_ai_budget_credits()
            if ceiling and _spent_today(conn) + credits > ceiling:
                raise BudgetError("Daily spending ceiling reached.")
        available = sum(r["remaining"] for r in _live_grants(conn, user_id, now))
        if available < credits and not unlimited:
            raise QuotaError(available, credits)
        if existing is not None:      # a released entry: reuse the row, keep the unique key
            ledger_id = int(existing["id"])
            conn.execute(
                "UPDATE credit_ledger SET credits=?, status=?, updated_at=? WHERE id=?",
                (credits, RESERVED, now, ledger_id))
            conn.execute("DELETE FROM credit_allocations WHERE ledger_id = ?", (ledger_id,))
        else:
            cur = conn.execute(
                "INSERT INTO credit_ledger (user_id, ref, kind, credits, status, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?)", (user_id, ref, kind, credits, RESERVED, now, now))
            ledger_id = int(cur.lastrowid)
        if not unlimited:
            _take(conn, ledger_id, user_id, credits, now)
        return ledger_id


def commit(ledger_id: int, actual: Optional[int] = None) -> int:
    """The work succeeded. Returns the credits finally charged.

    ``actual`` trues the amount up or down: less than reserved refunds the
    difference, more takes it from what is left (never failing the finished
    job: if the balance cannot cover it, the shortfall is simply not charged).
    """
    now = db.now()
    with db.write_connection() as conn:
        row = conn.execute("SELECT * FROM credit_ledger WHERE id = ?", (ledger_id,)).fetchone()
        if row is None or row["status"] != RESERVED:
            return int(row["credits"]) if row is not None and row["status"] == COMMITTED else 0
        charged = int(row["credits"])
        if actual is not None and int(actual) != charged:
            actual = max(0, int(actual))
            if actual < charged:
                _give_back(conn, ledger_id, charged - actual)
                charged = actual
            elif is_unlimited(int(row["user_id"])):
                charged = actual
            else:
                charged += _take(conn, ledger_id, int(row["user_id"]), actual - charged, now)
        conn.execute("UPDATE credit_ledger SET status=?, credits=?, cost_usd=?, updated_at=? WHERE id=?",
                     (COMMITTED, charged, plans.estimated_cost_usd(row["kind"], charged), now, ledger_id))
        return charged


def release(ledger_id: int) -> int:
    """The work failed: refund the whole reservation. Returns what was refunded."""
    now = db.now()
    with db.write_connection() as conn:
        row = conn.execute("SELECT * FROM credit_ledger WHERE id = ?", (ledger_id,)).fetchone()
        if row is None or row["status"] != RESERVED:
            return 0
        back = _give_back(conn, ledger_id, int(row["credits"]))
        conn.execute("UPDATE credit_ledger SET status=?, updated_at=? WHERE id=?",
                     (RELEASED, now, ledger_id))
        return back


def reservation_for(ref: str, kind: str) -> Optional[dict]:
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM credit_ledger WHERE ref = ? AND kind = ?",
                           (ref, kind)).fetchone()
    return dict(row) if row else None


def can_afford(user_id: int, credits: int) -> None:
    """Raise QuotaError unless the account holds ``credits`` right now. Spends nothing."""
    if is_unlimited(user_id):
        return
    ensure_free_grant(user_id)
    with db.connection() as conn:
        available = sum(r["remaining"] for r in _live_grants(conn, user_id, db.now()))
    if available < int(credits):
        raise QuotaError(available, int(credits))


def spend_up_to(user_id: int, ref: str, kind: str, credits: int) -> int:
    """Charge ``credits`` for work that already happened, as much as the balance
    allows (a finished job must not fail because the estimate was low). Idempotent
    per ``(ref, kind)``. Returns the amount charged."""
    credits = max(0, int(credits))
    if credits == 0:
        return 0
    now = db.now()
    ensure_free_grant(user_id)
    unlimited = is_unlimited(user_id)
    with db.write_connection() as conn:
        existing = conn.execute(
            "SELECT credits, status FROM credit_ledger WHERE ref = ? AND kind = ?",
            (ref, kind)).fetchone()
        if existing is not None and existing["status"] != RELEASED:
            return 0
        if existing is not None:
            conn.execute("DELETE FROM credit_ledger WHERE ref = ? AND kind = ?", (ref, kind))
        cur = conn.execute(
            "INSERT INTO credit_ledger (user_id, ref, kind, credits, status, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)", (user_id, ref, kind, 0, COMMITTED, now, now))
        ledger_id = int(cur.lastrowid)
        taken = credits if unlimited else _take(conn, ledger_id, user_id, credits, now)
        conn.execute("UPDATE credit_ledger SET credits = ?, cost_usd = ? WHERE id = ?",
                     (taken, plans.estimated_cost_usd(kind, taken), ledger_id))
        return taken


def expire_stale_reservations(older_than_seconds: float = 6 * 3600) -> int:
    """Release reservations whose work never reported back (a crash, a restart).
    Called periodically so credits cannot stay locked forever."""
    cutoff = db.now() - older_than_seconds
    with db.connection() as conn:
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM credit_ledger WHERE status = ? AND updated_at < ?",
            (RESERVED, cutoff)).fetchall()]
    return sum(1 for i in ids if release(i))
