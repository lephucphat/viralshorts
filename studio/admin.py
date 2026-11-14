"""The operator's console: who signed up, what came in, what was spent, and the few
corrective actions (lock an account, give credits, take back a refunded payment).

Access: the signed-in user's verified email must be listed in ``ADMIN_EMAILS``
(``auth.User.is_admin``). There is no admin flag in the database to flip by accident.
Every action writes an ``admin_audit`` row.

Refunding money is done in the provider's own dashboard (Stripe / PayOS); marking the
payment refunded here takes the credits back and cancels the plan the payment bought.
"""

import csv
import io
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from . import archive, auth, credits, db, lifecycle, mailer, plans, promo, projects
from .api import current_user
from .payments import enabled_providers, service, stripe_provider

MAX_GRANT = 100_000


class GrantBody(BaseModel):
    credits: int
    note: str = ""


class RefundBody(BaseModel):
    note: str = ""


class PlanBody(BaseModel):
    plan: str
    days: int = 30
    note: str = ""


class PromoBody(BaseModel):
    code: str
    credits: int
    max_uses: int = 0
    expires_at: Optional[float] = None
    note: str = ""


class ActiveBody(BaseModel):
    active: bool


def vnd_per_usd() -> float:
    """Exchange rate used to put VND revenue next to the AI bill (which is in USD)."""
    try:
        return max(1.0, float(os.environ.get("VND_PER_USD", "25000")))
    except ValueError:
        return 25000.0


def to_usd(amount: float, currency: str) -> float:
    """``amount`` is in the currency's smallest unit as stored: cents for USD, dong for VND."""
    currency = (currency or "").lower()
    if currency == "usd":
        return amount / 100.0
    if currency == "vnd":
        return amount / vnd_per_usd()
    return 0.0


def _fail(status: int, code: str, message: str):
    return HTTPException(status_code=status, detail={"error": code, "message": message})


def require_admin(user: auth.User = Depends(current_user)) -> auth.User:
    if not user.is_admin:
        # 404, not 403: do not confirm that an admin console exists.
        raise _fail(404, "not_found", "Not found.")
    return user


def audit(conn, admin_id: int, action: str, user_id: Optional[int], detail: dict) -> None:
    conn.execute("INSERT INTO admin_audit (admin_id, action, user_id, detail, created_at) VALUES (?,?,?,?,?)",
                 (admin_id, action, user_id, json.dumps(detail, ensure_ascii=False), db.now()))


# ---- reads ----------------------------------------------------------------------------------
def overview() -> dict:
    now = db.now()
    d30 = now - 30 * 86400
    with db.connection() as conn:
        one = lambda sql, *a: conn.execute(sql, a).fetchone()[0]
        revenue = {}
        for r in conn.execute(
                "SELECT currency, "
                "SUM(CASE WHEN status='paid' THEN amount ELSE 0 END) AS total, "
                "SUM(CASE WHEN status='paid' AND paid_at > ? THEN amount ELSE 0 END) AS last30, "
                "SUM(CASE WHEN status='refunded' THEN amount ELSE 0 END) AS refunded "
                "FROM payments GROUP BY currency", (d30,)):
            revenue[r["currency"]] = {"total": r["total"] or 0, "last_30d": r["last30"] or 0,
                                      "refunded": r["refunded"] or 0}
        spend = {r["kind"]: r["c"] for r in conn.execute(
            "SELECT kind, SUM(credits) AS c FROM credit_ledger "
            "WHERE status IN ('reserved','committed') AND created_at > ? GROUP BY kind", (d30,))}
        by_plan = {r["plan"]: r["n"] for r in conn.execute("SELECT plan, COUNT(*) AS n FROM users GROUP BY plan")}
        data = {
            "users": {
                "total": one("SELECT COUNT(*) FROM users"),
                "last_7d": one("SELECT COUNT(*) FROM users WHERE created_at > ?", now - 7 * 86400),
                "verified": one("SELECT COUNT(*) FROM users WHERE email_verified_at IS NOT NULL"),
                "disabled": one("SELECT COUNT(*) FROM users WHERE disabled_at IS NOT NULL"),
                "by_plan": by_plan,
            },
            "paying": one("SELECT COUNT(DISTINCT user_id) FROM subscriptions WHERE status IN ('active','trialing','past_due')"),
            "revenue": revenue,
            "credits_spent_30d": spend,
            "economics_30d": _economics(conn, d30),
            "invoice_requests": one("SELECT COUNT(*) FROM payments WHERE invoice_requested_at IS NOT NULL "
                                    "AND status = 'paid'"),
            "credits_spent_today": credits.spent_today(),
            "daily_budget": plans.daily_ai_budget_credits(),
            "mail_enabled": mailer.enabled(),
            "archive": archive.stats(),
            "providers": enabled_providers(),
        }
    return data


def _economics(conn, since: float) -> dict:
    """Money in, estimated AI bill out, over a window, in USD. The bill is the sum of the
    per-call estimates stored in the credit ledger (``plans.COST_USD_PER_CREDIT``), so it is
    a margin guide, not an invoice from Google or fal."""
    revenue = sum(to_usd(r["t"] or 0, r["currency"]) for r in conn.execute(
        "SELECT currency, SUM(amount) AS t FROM payments WHERE status = 'paid' AND paid_at > ? GROUP BY currency",
        (since,)))
    cost = conn.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM credit_ledger WHERE status = 'committed' "
                        "AND created_at > ?", (since,)).fetchone()[0]
    by_plan = {}
    for r in conn.execute(
            "SELECT u.plan AS plan, COALESCE(SUM(l.cost_usd), 0) AS cost, COALESCE(SUM(l.credits), 0) AS credits "
            "FROM credit_ledger l JOIN users u ON u.id = l.user_id "
            "WHERE l.status = 'committed' AND l.created_at > ? GROUP BY u.plan", (since,)):
        by_plan[r["plan"]] = {"cost_usd": round(r["cost"], 2), "credits": r["credits"], "revenue_usd": 0.0}
    for r in conn.execute(
            "SELECT u.plan AS plan, p.currency AS currency, SUM(p.amount) AS t FROM payments p "
            "JOIN users u ON u.id = p.user_id WHERE p.status = 'paid' AND p.paid_at > ? "
            "GROUP BY u.plan, p.currency", (since,)):
        row = by_plan.setdefault(r["plan"], {"cost_usd": 0.0, "credits": 0, "revenue_usd": 0.0})
        row["revenue_usd"] = round(row["revenue_usd"] + to_usd(r["t"] or 0, r["currency"]), 2)
    for row in by_plan.values():
        row["margin_usd"] = round(row["revenue_usd"] - row["cost_usd"], 2)
    return {"revenue_usd": round(revenue, 2), "ai_cost_usd": round(cost, 2),
            "margin_usd": round(revenue - cost, 2), "vnd_per_usd": vnd_per_usd(), "by_plan": by_plan}


def series(days: int = 30) -> list:
    """One row per day (UTC), oldest first: money in, credits spent, AI cost, sign-ups."""
    days = max(1, min(int(days), 365))
    start = (datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
             - (days - 1) * 86400)
    rows = {datetime.fromtimestamp(start + i * 86400, tz=timezone.utc).strftime("%Y-%m-%d"):
            {"revenue_usd": 0.0, "credits": 0, "cost_usd": 0.0, "signups": 0} for i in range(days)}
    with db.connection() as conn:
        for r in conn.execute("SELECT strftime('%Y-%m-%d', paid_at, 'unixepoch') AS d, currency, SUM(amount) AS t "
                              "FROM payments WHERE status = 'paid' AND paid_at >= ? GROUP BY d, currency", (start,)):
            if r["d"] in rows:
                rows[r["d"]]["revenue_usd"] += to_usd(r["t"] or 0, r["currency"])
        for r in conn.execute("SELECT strftime('%Y-%m-%d', created_at, 'unixepoch') AS d, SUM(credits) AS c, "
                              "COALESCE(SUM(cost_usd), 0) AS k FROM credit_ledger WHERE status = 'committed' "
                              "AND created_at >= ? GROUP BY d", (start,)):
            if r["d"] in rows:
                rows[r["d"]]["credits"], rows[r["d"]]["cost_usd"] = r["c"] or 0, r["k"] or 0.0
        for r in conn.execute("SELECT strftime('%Y-%m-%d', created_at, 'unixepoch') AS d, COUNT(*) AS n "
                              "FROM users WHERE created_at >= ? GROUP BY d", (start,)):
            if r["d"] in rows:
                rows[r["d"]]["signups"] = r["n"]
    return [{"day": d, **{k: round(v, 2) if isinstance(v, float) else v for k, v in vals.items()}}
            for d, vals in rows.items()]


def list_payments(status: str = "", provider: str = "", q: str = "", limit: int = 50, offset: int = 0) -> dict:
    where, args = [], []
    if status:
        where.append("p.status = ?")
        args.append(status)
    if provider:
        where.append("p.provider = ?")
        args.append(provider)
    if q.strip():
        where.append("(lower(u.email) LIKE ? OR p.provider_ref LIKE ?)")
        args += [f"%{q.strip().lower()}%"] * 2
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    limit = max(1, min(int(limit), 200))
    with db.connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM payments p JOIN users u ON u.id = p.user_id {clause}",
                             args).fetchone()[0]
        rows = conn.execute(
            "SELECT p.id, p.user_id, u.email, p.provider, p.provider_ref, p.kind, p.item, p.amount, p.currency, "
            "p.credits, p.status, p.created_at, p.paid_at, p.invoice_requested_at "
            f"FROM payments p JOIN users u ON u.id = p.user_id {clause} ORDER BY p.id DESC LIMIT ? OFFSET ?",
            [*args, limit, int(offset)]).fetchall()
    return {"total": total, "payments": [dict(r) for r in rows]}


def list_subscriptions(status: str = "", limit: int = 50, offset: int = 0) -> dict:
    where, args = ("WHERE s.status = ?", [status]) if status else ("", [])
    limit = max(1, min(int(limit), 200))
    with db.connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM subscriptions s {where}", args).fetchone()[0]
        rows = conn.execute(
            "SELECT s.id, s.user_id, u.email, s.provider, s.plan, s.status, s.current_period_start, "
            "s.current_period_end, s.cancel_at_period_end FROM subscriptions s JOIN users u ON u.id = s.user_id "
            f"{where} ORDER BY s.id DESC LIMIT ? OFFSET ?", [*args, limit, int(offset)]).fetchall()
    return {"total": total, "subscriptions": [{**dict(r), "cancel_at_period_end": bool(r["cancel_at_period_end"])}
                                              for r in rows]}


def failed_projects(limit: int = 50) -> list:
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT p.job_id, p.user_id, u.email, p.title, p.source_kind, p.status, p.minutes_charged, "
            "p.created_at, p.updated_at FROM projects p JOIN users u ON u.id = p.user_id "
            "WHERE p.status IN ('failed','error') ORDER BY p.updated_at DESC LIMIT ?",
            (max(1, min(int(limit), 200)),)).fetchall()
    return [dict(r) for r in rows]


def webhook_events(limit: int = 100) -> list:
    with db.connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT id, provider, event_id, type, created_at FROM payment_events ORDER BY id DESC LIMIT ?",
            (max(1, min(int(limit), 500)),))]


def invoice_requests() -> list:
    """Paid payments whose customer asked for an invoice, with the details to print on it."""
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT p.id, p.user_id, u.email, p.provider, p.provider_ref, p.item, p.amount, p.currency, "
            "p.paid_at, p.invoice_requested_at, b.company, b.tax_code, b.address, b.email AS invoice_email "
            "FROM payments p JOIN users u ON u.id = p.user_id LEFT JOIN billing_info b ON b.user_id = p.user_id "
            "WHERE p.invoice_requested_at IS NOT NULL AND p.status = 'paid' "
            "ORDER BY p.invoice_requested_at DESC LIMIT 200").fetchall()
    return [dict(r) for r in rows]


def _cell(v) -> str:
    """A spreadsheet runs a cell that starts with = + - @ as a formula: defuse user text."""
    text = "" if v is None else str(v)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def export_csv(kind: str) -> str:
    if kind == "users":
        sql = ("SELECT id, email, name, plan, created_at, last_login_at, email_verified_at, disabled_at "
               "FROM users ORDER BY id")
    elif kind == "payments":
        sql = ("SELECT p.id, u.email, p.provider, p.provider_ref, p.kind, p.item, p.amount, p.currency, "
               "p.credits, p.status, p.created_at, p.paid_at FROM payments p JOIN users u ON u.id = p.user_id "
               "ORDER BY p.id")
    else:
        raise _fail(400, "bad_kind", "Export users or payments.")
    out = io.StringIO()
    writer = csv.writer(out)
    with db.connection() as conn:
        cur = conn.execute(sql)
        writer.writerow([c[0] for c in cur.description])
        for row in cur:
            writer.writerow([_cell(v) for v in tuple(row)])
    return out.getvalue()


def list_users(q: str = "", limit: int = 50, offset: int = 0) -> dict:
    limit = max(1, min(int(limit), 200))
    like = f"%{q.strip().lower()}%"
    now = db.now()
    where, args = ("", [])
    if q.strip():
        where, args = "WHERE lower(u.email) LIKE ? OR lower(u.name) LIKE ?", [like, like]
    with db.connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM users u {where}", args).fetchone()[0]
        rows = conn.execute(
            "SELECT u.id, u.email, u.name, u.plan, u.created_at, u.last_login_at, u.email_verified_at, "
            "u.disabled_at, COALESCE((SELECT SUM(remaining) FROM credit_grants g WHERE g.user_id = u.id "
            "AND g.remaining > 0 AND (g.expires_at IS NULL OR g.expires_at > ?)), 0) AS credits_left "
            f"FROM users u {where} ORDER BY u.id DESC LIMIT ? OFFSET ?", [now, *args, limit, int(offset)]).fetchall()
    return {"total": total, "users": [_user_row(r) for r in rows]}


def _user_row(r) -> dict:
    return {"id": r["id"], "email": r["email"], "name": r["name"], "plan": r["plan"],
            "created_at": r["created_at"], "last_login_at": r["last_login_at"],
            "verified": r["email_verified_at"] is not None, "disabled": r["disabled_at"] is not None,
            "credits_left": int(r["credits_left"])}


def user_detail(user_id: int) -> Optional[dict]:
    with db.connection() as conn:
        u = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if u is None:
            return None
        pays = [dict(r) for r in conn.execute(
            "SELECT id, provider, provider_ref, kind, item, amount, currency, credits, status, created_at, paid_at "
            "FROM payments WHERE user_id = ? ORDER BY created_at DESC LIMIT 50", (user_id,))]
        ledger = [dict(r) for r in conn.execute(
            "SELECT kind, ref, credits, status, created_at FROM credit_ledger WHERE user_id = ? "
            "ORDER BY id DESC LIMIT 30", (user_id,))]
        projects_n = conn.execute("SELECT COUNT(*) FROM projects WHERE user_id = ?", (user_id,)).fetchone()[0]
        subs = [dict(r) for r in conn.execute(
            "SELECT id, provider, plan, status, current_period_end, cancel_at_period_end FROM subscriptions "
            "WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user_id,))]
        cost = conn.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM credit_ledger WHERE user_id = ? "
                            "AND status = 'committed'", (user_id,)).fetchone()[0]
        revenue = sum(to_usd(r["t"] or 0, r["currency"]) for r in conn.execute(
            "SELECT currency, SUM(amount) AS t FROM payments WHERE user_id = ? AND status = 'paid' "
            "GROUP BY currency", (user_id,)))
    bal = credits.balance(user_id)
    return {"id": u["id"], "email": u["email"], "name": u["name"], "plan": u["plan"],
            "created_at": u["created_at"], "last_login_at": u["last_login_at"],
            "verified": u["email_verified_at"] is not None, "disabled": u["disabled_at"] is not None,
            "has_google": bool(u["google_sub"]), "projects": projects_n,
            "credits": bal, "payments": pays, "ledger": ledger, "subscriptions": subs,
            "ai_cost_usd": round(cost, 2), "revenue_usd": round(revenue, 2),
            "billing_info": service.get_billing_info(user_id)}


def audit_log(limit: int = 100, offset: int = 0, action: str = "", user_id: Optional[int] = None) -> list:
    where, args = [], []
    if action:
        where.append("a.action = ?")
        args.append(action)
    if user_id:
        where.append("a.user_id = ?")
        args.append(int(user_id))
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT a.id, a.action, a.user_id, a.detail, a.created_at, "
            "(SELECT email FROM users WHERE id = a.admin_id) AS admin_email, "
            "(SELECT email FROM users WHERE id = a.user_id) AS user_email "
            f"FROM admin_audit a {clause} ORDER BY a.id DESC LIMIT ? OFFSET ?",
            [*args, max(1, min(int(limit), 500)), max(0, int(offset))]).fetchall()
    return [{**dict(r), "detail": json.loads(r["detail"] or "{}")} for r in rows]


# ---- actions --------------------------------------------------------------------------------
def set_disabled(admin_id: int, user_id: int, disabled: bool) -> None:
    if admin_id == user_id:
        raise _fail(400, "self_action", "You cannot lock your own account.")
    with db.write_connection() as conn:
        if conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
            raise _fail(404, "not_found", "No such user.")
        # token_version + 1 ends every session now, not at the next login.
        conn.execute("UPDATE users SET disabled_at = ?, token_version = token_version + 1 WHERE id = ?",
                     (db.now() if disabled else None, user_id))
        audit(conn, admin_id, "disable" if disabled else "enable", user_id, {})


def grant_credits(admin_id: int, user_id: int, amount: int, note: str) -> None:
    if not 1 <= amount <= MAX_GRANT:
        raise _fail(422, "bad_amount", f"Credits must be between 1 and {MAX_GRANT}.")
    with db.write_connection() as conn:
        if conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
            raise _fail(404, "not_found", "No such user.")
        credits.grant(user_id, "topup", amount, expires_at=None,
                      source_ref=f"admin:{uuid.uuid4().hex}", conn=conn)
        audit(conn, admin_id, "grant", user_id, {"credits": amount, "note": note[:200]})


def set_plan(admin_id: int, user_id: int, plan_id: str, days: int, note: str) -> dict:
    """Put a user on a plan by hand (a classmate's demo, compensation, a sponsor). It is a
    normal subscription row from the ``admin`` provider with its own credits and end date, so
    it expires like any other and never touches a card. ``free`` ends the manual ones."""
    if plan_id not in plans.PLANS:
        raise _fail(422, "bad_plan", "Unknown plan.")
    if not 1 <= int(days) <= 366:
        raise _fail(422, "bad_days", "Days must be between 1 and 366.")
    with db.write_connection() as conn:
        if conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
            raise _fail(404, "not_found", "No such user.")
        if plan_id == plans.DEFAULT_PLAN:
            conn.execute("UPDATE subscriptions SET status = 'canceled', updated_at = ? WHERE user_id = ? "
                         "AND provider = 'admin' AND status IN ('active','trialing','past_due')", (db.now(), user_id))
        else:
            ref = f"admin:{uuid.uuid4().hex}"
            now = db.now()
            end = now + int(days) * 86400
            service.upsert_subscription(conn, user_id, "admin", ref, plan_id, "active", now, end)
            service.grant_period_credits(conn, user_id, plan_id, ref, end)
        after = service.refresh_user_plan(conn, user_id)
        audit(conn, admin_id, "set_plan", user_id, {"plan": plan_id, "days": int(days), "note": note[:200],
                                                     "plan_after": after})
    return {"plan": after}


def verify_email(admin_id: int, user_id: int) -> None:
    with db.write_connection() as conn:
        if conn.execute("UPDATE users SET email_verified_at = COALESCE(email_verified_at, ?) WHERE id = ?",
                        (db.now(), user_id)).rowcount != 1:
            raise _fail(404, "not_found", "No such user.")
        audit(conn, admin_id, "verify_email", user_id, {})


def send_reset(admin_id: int, user_id: int) -> None:
    with db.write_connection() as conn:
        row = conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise _fail(404, "not_found", "No such user.")
        audit(conn, admin_id, "send_reset", user_id, {})
    lifecycle.request_reset(row["email"])


def delete_user(admin_id: int, user_id: int, remove_files: Optional[Callable[[str], None]] = None) -> dict:
    """Erase an account for good (a request that arrived by email, a spam account).

    Same order as the owner's own deletion: card subscriptions are cancelled at Stripe first
    and a failure aborts, so nobody is billed for an account that is gone. Another admin's
    account is refused, and so is one's own."""
    if admin_id == user_id:
        raise _fail(400, "self_action", "You cannot delete your own account here.")
    with db.connection() as conn:
        row = conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise _fail(404, "not_found", "No such user.")
    if row["email"].lower() in auth.admin_emails():
        raise _fail(403, "admin_account", "Remove this address from ADMIN_EMAILS before deleting it.")
    if stripe_provider.secret_key():
        for sub_id in service.live_subscription_refs(user_id, "stripe"):
            try:
                stripe_provider.cancel_subscription(sub_id)
            except stripe_provider.StripeError:
                raise _fail(502, "cancel_failed", "Could not cancel the card subscription; nothing was deleted.")
    job_ids = projects.job_ids_for_user(user_id)
    auth.erase_account(user_id)
    for job_id in job_ids:
        if remove_files:
            remove_files(job_id)
    with db.write_connection() as conn:
        audit(conn, admin_id, "delete_user", None, {"email": row["email"], "projects": len(job_ids)})
    return {"deleted": True}


grant_ref_of = service.grant_ref_of


def refund_payment(admin_id: int, payment_id: int, note: str) -> dict:
    """Record that a payment was refunded (in the provider's dashboard): take back the credits
    it bought that are still unspent and, for a plan, end the plan it paid for.

    A card subscription keeps billing until Stripe is told to stop, so it is cancelled there
    too (after the database change commits). If that call fails the refund is still recorded
    and ``provider_cancel_failed`` lists the subscriptions to cancel by hand."""
    with db.write_connection() as conn:
        p = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
        if p is None:
            raise _fail(404, "not_found", "No such payment.")
        if p["status"] != "paid":
            raise _fail(409, "not_refundable", "Only a paid payment can be marked refunded.")
        outcome = service.reverse_payment(conn, p, "refunded")
        failed = []
        audit(conn, admin_id, "refund", p["user_id"],
              {"payment_id": payment_id, "clawed_back": outcome["clawed_back"],
               "unrecovered": outcome["unrecovered"], "plan_after": outcome["plan_after"],
               "note": note[:200]})
    for sub_id in outcome["stripe_subscriptions"]:
        try:
            stripe_provider.cancel_subscription(sub_id)
        except stripe_provider.StripeError:
            failed.append(sub_id)
    return {"refunded": True, "clawed_back": outcome["clawed_back"],
            "unrecovered": outcome["unrecovered"], "plan": outcome["plan_after"],
            "provider_cancel_failed": failed}


# ---- routes ---------------------------------------------------------------------------------
def build_router(remove_files: Optional[Callable[[str], None]] = None) -> APIRouter:
    router = APIRouter(prefix="/api/admin")

    @router.get("/overview")
    def get_overview(_: auth.User = Depends(require_admin)):
        return overview()

    @router.get("/users")
    def get_users(q: str = "", limit: int = 50, offset: int = 0, _: auth.User = Depends(require_admin)):
        return list_users(q, limit, offset)

    @router.get("/users/{user_id}")
    def get_user(user_id: int, _: auth.User = Depends(require_admin)):
        detail = user_detail(user_id)
        if detail is None:
            raise _fail(404, "not_found", "No such user.")
        return detail

    @router.post("/users/{user_id}/disable")
    def disable(user_id: int, admin: auth.User = Depends(require_admin)):
        set_disabled(admin.id, user_id, True)
        return {"ok": True}

    @router.post("/users/{user_id}/enable")
    def enable(user_id: int, admin: auth.User = Depends(require_admin)):
        set_disabled(admin.id, user_id, False)
        return {"ok": True}

    @router.post("/users/{user_id}/grant")
    def grant(user_id: int, body: GrantBody, admin: auth.User = Depends(require_admin)):
        grant_credits(admin.id, user_id, body.credits, body.note)
        return {"ok": True}

    @router.post("/payments/{payment_id}/refund")
    def refund(payment_id: int, body: RefundBody, admin: auth.User = Depends(require_admin)):
        return refund_payment(admin.id, payment_id, body.note)

    @router.get("/audit")
    def get_audit(limit: int = 100, offset: int = 0, action: str = "", user_id: Optional[int] = None,
                  _: auth.User = Depends(require_admin)):
        return {"entries": audit_log(limit, offset, action, user_id)}

    @router.get("/series")
    def get_series(days: int = 30, _: auth.User = Depends(require_admin)):
        return {"days": series(days)}

    @router.get("/payments")
    def get_payments(status: str = "", provider: str = "", q: str = "", limit: int = 50, offset: int = 0,
                     _: auth.User = Depends(require_admin)):
        return list_payments(status, provider, q, limit, offset)

    @router.get("/subscriptions")
    def get_subscriptions(status: str = "", limit: int = 50, offset: int = 0,
                          _: auth.User = Depends(require_admin)):
        return list_subscriptions(status, limit, offset)

    @router.get("/failed-projects")
    def get_failed(limit: int = 50, _: auth.User = Depends(require_admin)):
        return {"projects": failed_projects(limit)}

    @router.get("/webhook-events")
    def get_events(limit: int = 100, _: auth.User = Depends(require_admin)):
        return {"events": webhook_events(limit)}

    @router.get("/invoice-requests")
    def get_invoice_requests(_: auth.User = Depends(require_admin)):
        return {"requests": invoice_requests()}

    @router.get("/export/{kind}")
    def get_export(kind: str, admin: auth.User = Depends(require_admin)):
        body = export_csv(kind)
        with db.write_connection() as conn:
            audit(conn, admin.id, "export", None, {"kind": kind})
        return Response(body, media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{kind}.csv"'})

    @router.post("/users/{user_id}/plan")
    def post_plan(user_id: int, body: PlanBody, admin: auth.User = Depends(require_admin)):
        return set_plan(admin.id, user_id, body.plan, body.days, body.note)

    @router.post("/users/{user_id}/verify-email")
    def post_verify(user_id: int, admin: auth.User = Depends(require_admin)):
        verify_email(admin.id, user_id)
        return {"ok": True}

    @router.post("/users/{user_id}/send-reset")
    def post_reset(user_id: int, admin: auth.User = Depends(require_admin)):
        send_reset(admin.id, user_id)
        return {"ok": True}

    @router.delete("/users/{user_id}")
    def delete(user_id: int, admin: auth.User = Depends(require_admin)):
        return delete_user(admin.id, user_id, remove_files)

    # ---- promo codes ----------------------------------------------------------------------
    @router.get("/promos")
    def get_promos(_: auth.User = Depends(require_admin)):
        return {"codes": promo.list_codes()}

    @router.post("/promos")
    def post_promo(body: PromoBody, admin: auth.User = Depends(require_admin)):
        try:
            created = promo.create(body.code, body.credits, body.max_uses, body.expires_at, body.note)
        except promo.PromoError as e:
            raise _fail(e.status, e.code, e.message)
        with db.write_connection() as conn:
            audit(conn, admin.id, "promo_create", None, {"code": created["code"], "credits": created["credits"]})
        return created

    @router.post("/promos/{code}/active")
    def post_promo_active(code: str, body: ActiveBody, admin: auth.User = Depends(require_admin)):
        if not promo.set_active(code, body.active):
            raise _fail(404, "not_found", "No such code.")
        with db.write_connection() as conn:
            audit(conn, admin.id, "promo_on" if body.active else "promo_off", None, {"code": code})
        return {"ok": True}

    return router
