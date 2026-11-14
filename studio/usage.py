"""Monthly minutes allowance.

Billing is by minutes of SOURCE video, charged when a job finishes
successfully: a failed or cancelled job costs nothing, so there is no
reservation to release. Before a job starts we only check that the account has
something left. ``STUDIO_MONTHLY_MINUTES`` sets the allowance (0 = unlimited).
"""

import math
import os
from datetime import datetime, timezone

from . import db


class QuotaError(Exception):
    def __init__(self, remaining: int, limit: int):
        super().__init__("Monthly minutes used up.")
        self.remaining = remaining
        self.limit = limit


def monthly_limit() -> int:
    try:
        return max(0, int(os.environ.get("STUDIO_MONTHLY_MINUTES", "300")))
    except ValueError:
        return 300


def minutes_for(seconds: float) -> int:
    """Whole minutes billed for a source of this length (minimum 1)."""
    return max(1, int(math.ceil(float(seconds or 0) / 60.0)))


def _month_start(ts: float = None) -> float:
    dt = datetime.fromtimestamp(ts if ts is not None else db.now(), tz=timezone.utc)
    return datetime(dt.year, dt.month, 1, tzinfo=timezone.utc).timestamp()


def used_minutes(user_id: int) -> int:
    with db.connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(minutes), 0) AS m FROM usage_ledger "
            "WHERE user_id = ? AND created_at >= ?", (user_id, _month_start())).fetchone()
    return int(row["m"])


def _paid_summary(user_id: int) -> dict:
    from . import credits, plans
    bal = credits.balance(user_id)
    with db.connection() as conn:
        row = conn.execute("SELECT plan FROM users WHERE id = ?", (user_id,)).fetchone()
    plan = plans.get_plan(row["plan"] if row else None)
    limit = bal["plan_total"] + bal["topup_remaining"]
    return {
        # Same four keys the free allowance returns, so the existing meter still works.
        "limit": limit,
        "used": credits.used_this_month(user_id),
        "remaining": bal["remaining"],
        "unlimited": credits.is_unlimited(user_id),
        # What the paid edition adds.
        "paid": True,
        "plan": plan.id,
        "plan_name": plan.name,
        "credits": bal,
        "max_active_jobs": plan.max_active_jobs,
        "retention_days": plan.retention_days,
        "features": sorted(plan.features),
    }


def summary(user_id: int) -> dict:
    from . import plans
    if plans.paid_mode():
        return _paid_summary(user_id)
    limit = monthly_limit()
    used = used_minutes(user_id)
    return {
        "limit": limit,
        "used": used,
        "remaining": None if limit == 0 else max(0, limit - used),
        "unlimited": limit == 0,
    }


def check_can_start(user_id: int, estimated_minutes: int = 1) -> None:
    """Raise QuotaError unless the account can afford a job of this size."""
    from . import credits, plans
    if plans.paid_mode():
        try:
            credits.can_afford(user_id, estimated_minutes)
        except credits.QuotaError as e:
            raise QuotaError(e.remaining, e.required)
        return
    limit = monthly_limit()
    if limit == 0:
        return
    remaining = limit - used_minutes(user_id)
    if remaining < max(1, int(estimated_minutes)):
        raise QuotaError(max(0, remaining), limit)


def charge(user_id: int, job_id: str, minutes: int, kind: str = "process") -> bool:
    """Record the charge once per (job, kind). False if it was already recorded."""
    from . import credits, plans
    if plans.paid_mode():
        return credits.spend_up_to(user_id, job_id, kind, minutes) > 0
    with db.connection() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO usage_ledger (user_id, job_id, minutes, kind, created_at) "
            "VALUES (?,?,?,?,?)", (user_id, job_id, int(minutes), kind, db.now()))
        return cur.rowcount == 1
