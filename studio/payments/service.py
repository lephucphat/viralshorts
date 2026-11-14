"""Provider-neutral billing rules: who has which plan, and what a payment buys.

Stripe and PayOS translate their own webhooks into the few operations below, so
the rules (idempotency, which credits expire when, when a plan lapses) exist in
exactly one place and are tested without any network.

Every webhook handler runs inside ONE ``db.write_connection()`` transaction that
starts by claiming the event id: either the whole event is applied, or none of it
is and the provider's retry tries again. That is what makes a replayed or
concurrent webhook harmless.
"""

import re
import time
from typing import List, Optional

from .. import credits, db, plans, referral

ACTIVE_STATUSES = ("active", "trialing", "past_due")

# A card renewal is charged at the period boundary and its webhook can arrive a little
# later (or a retry after a failed charge), so a Stripe subscription keeps its plan for
# three days past its period end while it waits. A prepaid PayOS period has no renewal
# to wait for: it ends exactly when it ends.
_GRACE_SECONDS = 3 * 24 * 3600
_GRACE_SQL = f"(CASE WHEN provider = 'stripe' THEN {_GRACE_SECONDS} ELSE 0 END)"


class UnknownUser(Exception):
    """The event refers to a customer/subscription we cannot map to a user yet.
    The webhook answers 5xx so the provider retries after the other event that
    creates the mapping (for example ``checkout.session.completed``) has landed."""


# ---- idempotency ------------------------------------------------------------------------
def claim_event(conn, provider: str, event_id: str, event_type: str) -> bool:
    """True the first time an event id is seen, False for a replay."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO payment_events (provider, event_id, type, created_at) VALUES (?,?,?,?)",
        (provider, event_id, event_type, db.now()))
    return cur.rowcount == 1


# ---- users and customers ---------------------------------------------------------------
def customer_ref(provider: str, customer_id: str) -> str:
    return f"{provider}:{customer_id}"


def set_customer(conn, user_id: int, provider: str, customer_id: str) -> None:
    conn.execute("UPDATE users SET payment_customer_id = ? WHERE id = ?",
                 (customer_ref(provider, customer_id), user_id))


def user_by_customer(conn, provider: str, customer_id: str) -> Optional[int]:
    row = conn.execute("SELECT id FROM users WHERE payment_customer_id = ?",
                       (customer_ref(provider, customer_id),)).fetchone()
    return int(row["id"]) if row else None


def user_by_subscription(conn, provider: str, provider_ref: str) -> Optional[int]:
    row = conn.execute("SELECT user_id FROM subscriptions WHERE provider = ? AND provider_ref = ?",
                       (provider, provider_ref)).fetchone()
    return int(row["user_id"]) if row else None


def user_exists(conn, user_id) -> bool:
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return False
    return conn.execute("SELECT 1 FROM users WHERE id = ?", (uid,)).fetchone() is not None


# ---- plans and subscriptions -----------------------------------------------------------
def set_user_plan(conn, user_id: int, plan_id: str) -> None:
    conn.execute("UPDATE users SET plan = ? WHERE id = ?", (plans.get_plan(plan_id).id, user_id))


def upsert_subscription(conn, user_id: int, provider: str, provider_ref: str, plan_id: str,
                        status: str, period_start: Optional[float], period_end: Optional[float],
                        cancel_at_period_end: bool = False) -> None:
    now = db.now()
    conn.execute(
        "INSERT INTO subscriptions (user_id, provider, provider_ref, plan, status, "
        "current_period_start, current_period_end, cancel_at_period_end, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(provider, provider_ref) DO UPDATE SET plan=excluded.plan, status=excluded.status, "
        "current_period_start=COALESCE(excluded.current_period_start, current_period_start), "
        "current_period_end=COALESCE(excluded.current_period_end, current_period_end), "
        "cancel_at_period_end=excluded.cancel_at_period_end, updated_at=excluded.updated_at",
        (user_id, provider, provider_ref, plans.get_plan(plan_id).id, status, period_start,
         period_end, 1 if cancel_at_period_end else 0, now, now))


def refresh_user_plan(conn, user_id: int) -> str:
    """Set ``users.plan`` from the subscriptions that are still in force.

    The best active plan wins (a user cannot end up on free while a paid
    subscription runs), and with none left the user returns to free. Returns the
    resulting plan id.
    """
    now = db.now()
    rows = conn.execute(
        "SELECT plan FROM subscriptions WHERE user_id = ? AND status IN (?,?,?) "
        "AND (current_period_end IS NULL OR current_period_end + " + _GRACE_SQL + " > ?)",
        (user_id, *ACTIVE_STATUSES, now)).fetchall()
    order = list(plans.PLANS)               # free < starter < pro, as declared
    best = max((r["plan"] for r in rows), key=lambda p: order.index(p) if p in order else 0,
               default=plans.DEFAULT_PLAN)
    set_user_plan(conn, user_id, best)
    return best


def grant_period_credits(conn, user_id: int, plan_id: str, source_ref: str,
                         period_end: Optional[float]) -> bool:
    """The plan's credits for one billing period. They expire with the period, and
    ``source_ref`` (the invoice or payment id) makes a replay a no-op."""
    plan = plans.get_plan(plan_id)
    return credits.grant(user_id, "plan", plan.credits, expires_at=period_end,
                         source_ref=source_ref, conn=conn)


def grant_topup(conn, user_id: int, pack_id: str, source_ref: str) -> int:
    pack = plans.get_pack(pack_id)
    if pack is None:
        return 0
    return pack.credits if credits.grant(user_id, "topup", pack.credits, expires_at=None,
                                         source_ref=source_ref, conn=conn) else 0


def expire_due_subscriptions() -> int:
    """Move accounts whose paid period ended back to the free plan.

    Credits already expire on their own clock, so nobody keeps spending after the
    period; this only fixes the plan label (features, job cap, queue priority).
    Called every few minutes from the app's cleanup loop.
    """
    changed = 0
    with db.write_connection() as conn:
        now = db.now()
        stale = conn.execute(
            "SELECT DISTINCT user_id FROM subscriptions WHERE status IN (?,?,?) "
            "AND current_period_end IS NOT NULL AND current_period_end + " + _GRACE_SQL + " <= ?",
            (*ACTIVE_STATUSES, now)).fetchall()
        for row in stale:
            uid = int(row["user_id"])
            # A prepaid subscription (no auto-renew) simply ends; a Stripe one that is
            # still "active" past its period is waiting for its renewal event, so it
            # only lapses once the provider says so.
            conn.execute(
                "UPDATE subscriptions SET status = 'expired', updated_at = ? "
                "WHERE user_id = ? AND provider IN ('payos','admin') AND status IN (?,?,?) "
                "AND current_period_end <= ?", (now, uid, *ACTIVE_STATUSES, now))
            before = conn.execute("SELECT plan FROM users WHERE id = ?", (uid,)).fetchone()["plan"]
            if refresh_user_plan(conn, uid) != before:
                changed += 1
    return changed


def live_subscription_refs(user_id: int, provider: str) -> List[str]:
    """Provider-side ids of the subscriptions that could still charge this user."""
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT provider_ref FROM subscriptions WHERE user_id = ? AND provider = ? "
            "AND status IN (?,?,?,?)", (user_id, provider, *ACTIVE_STATUSES, "pending")).fetchall()
    return [r["provider_ref"] for r in rows]


def subscription_conflict(user_id: int, provider: str, plan_id: str) -> Optional[tuple]:
    """Why a new plan purchase must be refused, as ``(code, message)``, or None.

    A card subscription renews itself, so a second one would be billed in parallel with the
    first and nothing would ever cancel the old one: refuse it, and send the person to the
    billing portal (cancel there, buy the other plan when the period ends). A prepaid PayOS
    period does not renew, so buying the same plan again simply queues the next period, and a
    higher plan is allowed; going down while a higher plan is still paid for is not."""
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT provider, plan FROM subscriptions WHERE user_id = ? AND status IN (?,?,?) "
            "AND (current_period_end IS NULL OR current_period_end + " + _GRACE_SQL + " > ?)",
            (user_id, *ACTIVE_STATUSES, db.now())).fetchall()
    if not rows:
        return None
    if provider == "stripe" or any(r["provider"] == "stripe" for r in rows):
        return ("already_subscribed",
                "You already have an active plan. Manage or cancel it in the billing portal, "
                "then choose a new plan when it ends.")
    order = list(plans.PLANS)
    idx = lambda p: order.index(p) if p in order else 0
    if idx(plan_id) < max(idx(r["plan"]) for r in rows):
        return ("downgrade_blocked",
                "Your current plan is higher and still paid for. You can choose this plan when it ends.")
    return None


def grant_ref_of(payment) -> str:
    """The ``credit_grants.source_ref`` the webhook used for this payment."""
    if payment["provider"] == "payos":
        return f"payos:order:{payment['provider_ref']}"
    prefix = "topup" if payment["kind"] == "topup" else "inv"
    return f"stripe:{prefix}:{payment['provider_ref']}"


def reverse_payment(conn, payment, status: str = "refunded") -> dict:
    """Take back what a payment bought: the unspent part of its credits, and for a plan,
    the subscription it paid for. Used by a refund or dispute webhook and by the admin button.

    Only credits still unspent can be taken back (``unrecovered`` reports the rest). Returns
    ``clawed_back``, ``unrecovered``, ``plan_after`` and ``stripe_subscriptions`` (provider
    ids the caller must cancel at Stripe after the transaction commits: Stripe keeps
    billing a card until told otherwise, and a later paid invoice must not revive it)."""
    grant = conn.execute("SELECT id, amount, remaining FROM credit_grants WHERE source_ref = ?",
                         (grant_ref_of(payment),)).fetchone()
    clawed = unrecovered = 0
    if grant is not None:
        clawed = int(grant["remaining"])
        unrecovered = max(0, int(grant["amount"]) - clawed)
        conn.execute("UPDATE credit_grants SET remaining = 0 WHERE id = ?", (grant["id"],))
    conn.execute("UPDATE payments SET status = ? WHERE id = ?", (status, payment["id"]))
    plan_after, to_cancel = None, []
    if payment["kind"] == "subscription":
        live = (*ACTIVE_STATUSES, "pending")
        marks = ",".join("?" * len(live))
        if payment["provider"] == "payos":
            rows = conn.execute(f"SELECT id, provider_ref FROM subscriptions WHERE user_id = ? "
                                f"AND provider = 'payos' AND provider_ref IN (?, ?) AND status IN ({marks})",
                                (payment["user_id"], f"order:{payment['provider_ref']}",
                                 payment["provider_ref"], *live)).fetchall()
        else:
            rows = conn.execute(f"SELECT id, provider_ref FROM subscriptions WHERE user_id = ? "
                                f"AND provider = ? AND plan = ? AND status IN ({marks})",
                                (payment["user_id"], payment["provider"], payment["item"], *live)).fetchall()
        for r in rows:
            conn.execute("UPDATE subscriptions SET status = 'canceled', updated_at = ? WHERE id = ?",
                         (db.now(), r["id"]))
            if payment["provider"] == "stripe":
                to_cancel.append(r["provider_ref"])
        plan_after = refresh_user_plan(conn, payment["user_id"])
    return {"clawed_back": clawed, "unrecovered": unrecovered, "plan_after": plan_after,
            "stripe_subscriptions": to_cancel}


def active_subscription(user_id: int) -> Optional[dict]:
    with db.connection() as conn:
        row = conn.execute(
            "SELECT * FROM subscriptions WHERE user_id = ? AND status IN (?,?,?) "
            "ORDER BY current_period_end DESC LIMIT 1", (user_id, *ACTIVE_STATUSES)).fetchone()
    return dict(row) if row else None


# ---- payment history --------------------------------------------------------------------
def record_payment(conn, user_id: int, provider: str, provider_ref: str, kind: str, item: str,
                   amount: int, currency: str, credits_granted: int, status: str,
                   paid_at: Optional[float] = None, aux: Optional[str] = None) -> None:
    """``aux`` is the provider's second id for the same money (Stripe's payment intent or
    charge), which is what its refund and dispute webhooks carry."""
    conn.execute(
        "INSERT INTO payments (user_id, provider, provider_ref, kind, item, amount, currency, "
        "credits, status, created_at, paid_at, provider_aux) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(provider, provider_ref) DO UPDATE SET status=excluded.status, "
        "credits=MAX(credits, excluded.credits), paid_at=COALESCE(excluded.paid_at, paid_at), "
        "amount=excluded.amount, provider_aux=COALESCE(excluded.provider_aux, provider_aux) "
        "WHERE payments.status NOT IN ('refunded','disputed')",
        (user_id, provider, provider_ref, kind, item, int(amount), currency.lower(),
         int(credits_granted), status, db.now(), paid_at, aux))
    if status == "paid":
        # A referred friend's first payment pays both sides, in this same transaction.
        referral.reward_first_payment(conn, user_id)


def payments_for_user(user_id: int, limit: int = 50) -> List[dict]:
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT id, provider, provider_ref, kind, item, amount, currency, credits, status, "
            "created_at, paid_at, invoice_requested_at FROM payments "
            "WHERE user_id = ? AND status != 'pending' "
            "ORDER BY created_at DESC LIMIT ?", (user_id, limit)).fetchall()
    return [dict(r) for r in rows]


def payment_for_user(user_id: int, payment_id: int) -> Optional[dict]:
    """One settled payment of this user (None when it is someone else's or unpaid)."""
    with db.connection() as conn:
        row = conn.execute(
            "SELECT id, provider, provider_ref, kind, item, amount, currency, credits, status, "
            "created_at, paid_at, invoice_requested_at FROM payments "
            "WHERE id = ? AND user_id = ? AND status IN ('paid','refunded','disputed')",
            (payment_id, user_id)).fetchone()
    return dict(row) if row else None


# ---- invoice details --------------------------------------------------------------------------
class BillingInfoError(Exception):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def get_billing_info(user_id: int) -> dict:
    with db.connection() as conn:
        row = conn.execute("SELECT company, tax_code, address, email FROM billing_info WHERE user_id = ?",
                           (user_id,)).fetchone()
    return dict(row) if row else {"company": "", "tax_code": "", "address": "", "email": ""}


def save_billing_info(user_id: int, company: str, tax_code: str, address: str, email: str) -> dict:
    """What the customer wants printed on an invoice. The tax code is checked for shape only
    (a Vietnamese MST is 10 digits, or 10 + a 3-digit branch suffix)."""
    company, address, email = (company or "").strip()[:200], (address or "").strip()[:300], (email or "").strip()[:120]
    tax_code = (tax_code or "").strip().replace(" ", "")[:20]
    if tax_code and not re.fullmatch(r"\d{10}(-?\d{3})?", tax_code):
        raise BillingInfoError("bad_tax_code", "A tax code has 10 digits, or 10 digits plus a 3-digit branch.")
    if email and not re.fullmatch(r"[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}", email):
        raise BillingInfoError("invalid_email", "Enter a valid email address.")
    with db.connection() as conn:
        conn.execute(
            "INSERT INTO billing_info (user_id, company, tax_code, address, email, updated_at) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET company=excluded.company, tax_code=excluded.tax_code, "
            "address=excluded.address, email=excluded.email, updated_at=excluded.updated_at",
            (user_id, company, tax_code, address, email, db.now()))
    return get_billing_info(user_id)


def request_invoice(user_id: int, payment_id: int) -> dict:
    """Mark a paid payment as 'please issue an invoice' (the operator issues it by hand or
    through an e-invoice provider). Needs the customer's company name and tax code first."""
    info = get_billing_info(user_id)
    if not info["company"] or not info["tax_code"]:
        raise BillingInfoError("billing_info_missing", "Fill in your company name and tax code first.")
    with db.connection() as conn:
        cur = conn.execute("UPDATE payments SET invoice_requested_at = COALESCE(invoice_requested_at, ?) "
                           "WHERE id = ? AND user_id = ? AND status = 'paid'", (db.now(), payment_id, user_id))
        if cur.rowcount != 1:
            raise BillingInfoError("not_found", "No such paid payment.", 404)
    return {"ok": True}


def set_cancel_flag(user_id: int, cancel: bool) -> int:
    """Remember that a card subscription will (not) renew, so the page is right at once
    instead of after Stripe's webhook. Returns how many subscriptions changed."""
    with db.connection() as conn:
        return conn.execute(
            "UPDATE subscriptions SET cancel_at_period_end = ?, updated_at = ? WHERE user_id = ? "
            "AND provider = 'stripe' AND status IN (?,?,?)",
            (1 if cancel else 0, db.now(), user_id, *ACTIVE_STATUSES)).rowcount


def now() -> float:
    return time.time()
