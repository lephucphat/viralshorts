"""Card payments through Stripe, over its plain REST API (no SDK, so nothing to install).

Prices are sent inline with each Checkout Session (``price_data``), so the Stripe
dashboard needs no products or prices: only the secret key and a webhook endpoint.

    STRIPE_SECRET_KEY       sk_test_... / sk_live_...
    STRIPE_WEBHOOK_SECRET   whsec_... (from the webhook endpoint or `stripe listen`)

Everything that changes an account happens in ``handle_event`` from a *verified*
webhook, never from the browser returning to the success URL: a person who merely
types that URL gets nothing.
"""

import hashlib
import hmac
import json
import logging
import os
import time
from typing import Optional

import httpx

from .. import db, plans
from . import frontend_url, service

log = logging.getLogger("studio.payments")

API = "https://api.stripe.com/v1"
PROVIDER = "stripe"
SIGNATURE_TOLERANCE_SECONDS = 300


class StripeError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


class SignatureError(Exception):
    pass


def secret_key() -> str:
    return os.environ.get("STRIPE_SECRET_KEY", "").strip()


def webhook_secret() -> str:
    return os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()


def configured() -> bool:
    return bool(secret_key() and webhook_secret())


# ---- REST helpers --------------------------------------------------------------------------
def _flatten(data: dict, prefix: str = "") -> list:
    """Stripe wants form fields like ``line_items[0][quantity]``."""
    out = []
    for key, value in data.items():
        name = f"{prefix}[{key}]" if prefix else str(key)
        if isinstance(value, dict):
            out.extend(_flatten(value, name))
        elif isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    out.extend(_flatten(item, f"{name}[{i}]"))
                else:
                    out.append((f"{name}[{i}]", str(item)))
        elif isinstance(value, bool):
            out.append((name, "true" if value else "false"))
        elif value is not None:
            out.append((name, str(value)))
    return out


def _post(path: str, data: dict) -> dict:
    if not secret_key():
        raise StripeError("Stripe is not configured.", 503)
    try:
        resp = httpx.post(f"{API}/{path}", data=_flatten(data), auth=(secret_key(), ""), timeout=30.0)
    except httpx.HTTPError as e:
        raise StripeError(f"Could not reach Stripe: {e}")
    body = resp.json() if resp.content else {}
    if resp.status_code >= 400:
        message = (body.get("error") or {}).get("message", "Stripe rejected the request.")
        raise StripeError(message, 502)
    return body


def _delete(path: str) -> dict:
    if not secret_key():
        raise StripeError("Stripe is not configured.", 503)
    try:
        resp = httpx.delete(f"{API}/{path}", auth=(secret_key(), ""), timeout=30.0)
    except httpx.HTTPError as e:
        raise StripeError(f"Could not reach Stripe: {e}")
    body = resp.json() if resp.content else {}
    if resp.status_code == 404 or (body.get("error") or {}).get("code") == "resource_missing":
        return {"status": "canceled"}              # already gone: the goal is met
    if resp.status_code >= 400:
        raise StripeError((body.get("error") or {}).get("message", "Stripe rejected the request."), 502)
    return body


def set_cancel_at_period_end(subscription_id: str, cancel: bool) -> None:
    """Stop (or un-stop) a card subscription from renewing; the plan runs to the end of the
    period that was already paid for."""
    _post(f"subscriptions/{subscription_id}", {"cancel_at_period_end": bool(cancel)})


def cancel_subscription(subscription_id: str) -> None:
    """Stop a card subscription now (Stripe sends ``customer.subscription.deleted`` after).
    Used when an account is deleted or a payment is refunded or disputed."""
    _delete(f"subscriptions/{subscription_id}")


# ---- creating payments -----------------------------------------------------------------------
def create_checkout(user_id: int, email: str, kind: str, item: str,
                    customer_id: Optional[str] = None) -> dict:
    """A hosted Checkout page for a plan (``kind='subscription'``) or a pack (``'topup'``)."""
    base = frontend_url()
    meta = {"user_id": user_id, "kind": kind, "item": item}
    if kind == "subscription":
        plan = plans.PLANS.get(item)
        if plan is None or not plan.price_usd_cents:
            raise StripeError("Unknown plan.", 400)
        line = {"quantity": 1, "price_data": {
            "currency": "usd", "unit_amount": plan.price_usd_cents,
            "recurring": {"interval": "month"},
            "product_data": {"name": f"ViralShorts {plan.name}",
                             "description": f"{plan.credits} credits every month"}}}
        body = {"mode": "subscription", "subscription_data": {"metadata": meta}}
    elif kind == "topup":
        pack = plans.get_pack(item)
        if pack is None:
            raise StripeError("Unknown credit pack.", 400)
        line = {"quantity": 1, "price_data": {
            "currency": "usd", "unit_amount": pack.price_usd_cents,
            "product_data": {"name": f"ViralShorts {pack.credits} credits"}}}
        # A real customer (so the billing portal opens for people who only ever topped up)
        # and a PDF invoice for the one-off payment, which Stripe skips by default.
        body = {"mode": "payment", "payment_intent_data": {"metadata": meta},
                "invoice_creation": {"enabled": True}}
        if not customer_id:
            body["customer_creation"] = "always"
    else:
        raise StripeError("Unknown purchase type.", 400)

    body.update({
        "line_items": [line],
        "client_reference_id": str(user_id),
        "metadata": meta,
        "allow_promotion_codes": True,
        "success_url": f"{base}/#/account?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{base}/#/pricing?checkout=cancelled",
    })
    if customer_id:
        body["customer"] = customer_id
    elif email:
        body["customer_email"] = email
    session = _post("checkout/sessions", body)
    return {"id": session["id"], "url": session["url"]}


def create_portal(customer_id: str) -> str:
    """Stripe's hosted page to update the card, cancel, and download invoices."""
    session = _post("billing_portal/sessions",
                    {"customer": customer_id, "return_url": f"{frontend_url()}/#/account"})
    return session["url"]


# ---- webhook verification --------------------------------------------------------------------
def verify_webhook(payload: bytes, header: str, secret: Optional[str] = None,
                   now: Optional[float] = None) -> dict:
    """Return the event if ``header`` (``Stripe-Signature``) is valid for ``payload``.

    Stripe signs ``"{timestamp}.{payload}"`` with HMAC-SHA256; a header may carry
    several ``v1`` signatures (during secret rotation). Old timestamps are refused
    so a captured request cannot be replayed later.
    """
    secret = secret if secret is not None else webhook_secret()
    if not secret or not header:
        raise SignatureError("missing signature")
    parts = {}
    for chunk in header.split(","):
        key, _, value = chunk.strip().partition("=")
        parts.setdefault(key, []).append(value)
    try:
        timestamp = int(parts.get("t", [""])[0])
    except ValueError:
        raise SignatureError("bad timestamp")
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, sig) for sig in parts.get("v1", [])):
        raise SignatureError("signature mismatch")
    if abs((now if now is not None else time.time()) - timestamp) > SIGNATURE_TOLERANCE_SECONDS:
        raise SignatureError("timestamp outside tolerance")
    try:
        return json.loads(payload)
    except ValueError:
        raise SignatureError("payload is not JSON")


# ---- applying events -------------------------------------------------------------------------
def _meta(obj: dict) -> dict:
    return obj.get("metadata") or {}


def _period_of(sub_or_invoice: dict):
    """(start, end) as epoch seconds, across Stripe API versions."""
    lines = (sub_or_invoice.get("lines") or {}).get("data") or []
    if lines and lines[0].get("period"):
        p = lines[0]["period"]
        return p.get("start"), p.get("end")
    items = (sub_or_invoice.get("items") or {}).get("data") or []
    start = sub_or_invoice.get("current_period_start") or (items[0].get("current_period_start") if items else None)
    end = sub_or_invoice.get("current_period_end") or (items[0].get("current_period_end") if items else None)
    return start, end


def _resolve_user(conn, obj: dict, sub_id: Optional[str]) -> Optional[int]:
    uid = service.user_by_subscription(conn, PROVIDER, sub_id) if sub_id else None
    if uid is None and obj.get("customer"):
        uid = service.user_by_customer(conn, PROVIDER, obj["customer"])
    if uid is None:
        candidates = [_meta(obj), _meta(obj.get("subscription_details") or {})]
        lines = (obj.get("lines") or {}).get("data") or []
        if lines:
            candidates.append(_meta(lines[0]))
        for meta in candidates:
            if service.user_exists(conn, meta.get("user_id")):
                uid = int(meta["user_id"])
                break
    return uid


def _plan_of(conn, obj: dict, sub_id: Optional[str]) -> Optional[str]:
    if sub_id:
        row = conn.execute("SELECT plan FROM subscriptions WHERE provider = ? AND provider_ref = ?",
                           (PROVIDER, sub_id)).fetchone()
        if row:
            return row["plan"]
    candidates = [_meta(obj), _meta(obj.get("subscription_details") or {})]
    lines = (obj.get("lines") or {}).get("data") or []
    if lines:
        candidates.append(_meta(lines[0]))
    for meta in candidates:
        if meta.get("item") in plans.PLANS:
            return meta["item"]
        if meta.get("plan") in plans.PLANS:
            return meta["plan"]
    return None


def _checkout_completed(conn, obj: dict) -> str:
    meta = _meta(obj)
    user_id = meta.get("user_id") or obj.get("client_reference_id")
    if not service.user_exists(conn, user_id):
        raise service.UnknownUser(f"checkout {obj.get('id')}")
    user_id = int(user_id)
    if obj.get("customer"):
        service.set_customer(conn, user_id, PROVIDER, obj["customer"])

    if obj.get("mode") == "subscription":
        sub_id, item = obj.get("subscription"), meta.get("item")
        if sub_id and item in plans.PLANS and conn.execute(
                "SELECT 1 FROM subscriptions WHERE provider = ? AND provider_ref = ?",
                (PROVIDER, sub_id)).fetchone() is None:
            # 'pending' is not an active status: the plan starts when the invoice is paid.
            service.upsert_subscription(conn, user_id, PROVIDER, sub_id, item, "pending", None, None)
        return "applied"

    if meta.get("kind") == "topup" and obj.get("payment_status") == "paid":
        pack = plans.get_pack(meta.get("item", ""))
        if pack is None:
            return "ignored"
        granted = service.grant_topup(conn, user_id, pack.id, f"stripe:topup:{obj['id']}")
        service.record_payment(conn, user_id, PROVIDER, obj["id"], "topup", pack.id,
                               obj.get("amount_total") or pack.price_usd_cents,
                               obj.get("currency") or "usd", granted or pack.credits, "paid", db.now(),
                               aux=obj.get("payment_intent"))
        return "applied"
    return "ignored"


def _invoice_paid(conn, obj: dict) -> str:
    sub_id = obj.get("subscription")
    if not sub_id:
        return "ignored"                           # not a subscription invoice: nothing to grant
    user_id = _resolve_user(conn, obj, sub_id)
    if user_id is None:
        raise service.UnknownUser(f"invoice {obj.get('id')}")
    plan_id = _plan_of(conn, obj, sub_id)
    if plan_id is None:
        # The event that names the plan (checkout.session.completed) may simply not have
        # landed yet. Raising rolls back the claim, so Stripe's retry gets another chance
        # instead of the payment being recorded as handled and lost.
        raise service.UnknownUser(f"plan of invoice {obj.get('id')}")
    existing = conn.execute("SELECT status FROM subscriptions WHERE provider = ? AND provider_ref = ?",
                            (PROVIDER, sub_id)).fetchone()
    if existing and existing["status"] == "canceled":
        # We cancelled this subscription (refund, dispute, deleted account). A late or
        # replayed paid invoice must not bring it back to life.
        return "ignored"
    start, end = _period_of(obj)
    if obj.get("customer"):
        service.set_customer(conn, user_id, PROVIDER, obj["customer"])
    service.upsert_subscription(conn, user_id, PROVIDER, sub_id, plan_id, "active", start, end)
    service.grant_period_credits(conn, user_id, plan_id, f"stripe:inv:{obj['id']}", end)
    service.refresh_user_plan(conn, user_id)
    service.record_payment(conn, user_id, PROVIDER, obj["id"], "subscription", plan_id,
                           obj.get("amount_paid") or 0, obj.get("currency") or "usd",
                           plans.get_plan(plan_id).credits, "paid", db.now(),
                           aux=obj.get("payment_intent") or obj.get("charge"))
    return "applied"


def _invoice_failed(conn, obj: dict) -> str:
    sub_id = obj.get("subscription")
    if sub_id:
        conn.execute("UPDATE subscriptions SET status = 'past_due', updated_at = ? "
                     "WHERE provider = ? AND provider_ref = ? AND status = 'active'",
                     (db.now(), PROVIDER, sub_id))
    return "applied"


def _subscription_changed(conn, obj: dict, deleted: bool) -> str:
    sub_id = obj.get("id")
    user_id = _resolve_user(conn, obj, sub_id)
    if user_id is None:
        raise service.UnknownUser(f"subscription {sub_id}")
    plan_id = _plan_of(conn, obj, sub_id)
    if plan_id is None:
        return "ignored"
    start, end = _period_of(obj)
    status = "canceled" if deleted else (obj.get("status") or "active")
    # Do not let an older 'incomplete' update undo what a paid invoice already activated.
    existing = conn.execute("SELECT status FROM subscriptions WHERE provider = ? AND provider_ref = ?",
                            (PROVIDER, sub_id)).fetchone()
    if existing and existing["status"] == "active" and status in ("incomplete", "pending"):
        return "ignored"
    if existing and existing["status"] == "canceled" and not deleted:
        return "ignored"                           # cancelled by us; Stripe has not caught up yet
    service.upsert_subscription(conn, user_id, PROVIDER, sub_id, plan_id, status, start, end,
                                bool(obj.get("cancel_at_period_end")))
    service.refresh_user_plan(conn, user_id)
    return "applied"


def _payment_for_charge(conn, charge_id, intent_id, invoice_id):
    """The paid payment a refund or dispute refers to, found by whichever id Stripe sent."""
    ids = [i for i in (charge_id, intent_id, invoice_id) if i]
    if not ids:
        return None
    marks = ",".join("?" * len(ids))
    return conn.execute(
        f"SELECT * FROM payments WHERE provider = ? AND status = 'paid' "
        f"AND (provider_aux IN ({marks}) OR provider_ref IN ({marks}))",
        (PROVIDER, *ids, *ids)).fetchone()


def _reverse(conn, payment, status: str, later: list) -> str:
    outcome = service.reverse_payment(conn, payment, status)
    later.extend(outcome["stripe_subscriptions"])
    return "applied"


def _charge_refunded(conn, obj: dict, later: list) -> str:
    amount, refunded = int(obj.get("amount") or 0), int(obj.get("amount_refunded") or 0)
    if not (obj.get("refunded") or (amount and refunded >= amount)):
        return "ignored"                           # a partial refund is a human decision
    payment = _payment_for_charge(conn, obj.get("id"), obj.get("payment_intent"), obj.get("invoice"))
    return _reverse(conn, payment, "refunded", later) if payment else "ignored"


def _dispute_created(conn, obj: dict, later: list) -> str:
    payment = _payment_for_charge(conn, obj.get("charge"), obj.get("payment_intent"), None)
    return _reverse(conn, payment, "disputed", later) if payment else "ignored"


_HANDLERS = {
    "checkout.session.completed": lambda c, o: _checkout_completed(c, o),
    "checkout.session.async_payment_succeeded": lambda c, o: _checkout_completed(c, o),
    "invoice.paid": lambda c, o: _invoice_paid(c, o),
    "invoice.payment_failed": lambda c, o: _invoice_failed(c, o),
    "customer.subscription.created": lambda c, o: _subscription_changed(c, o, False),
    "customer.subscription.updated": lambda c, o: _subscription_changed(c, o, False),
    "customer.subscription.deleted": lambda c, o: _subscription_changed(c, o, True),
}

# Handlers that may leave Stripe subscriptions to cancel once the transaction has committed.
_REVERSALS = {
    "charge.refunded": _charge_refunded,
    "charge.dispute.created": _dispute_created,
}


def handle_event(event: dict) -> str:
    """Apply one verified event. Returns ``applied``, ``duplicate`` or ``ignored``.

    Raises ``service.UnknownUser`` when the event arrived before the one that links
    it to an account; nothing is recorded then, so the provider's retry works.

    A full refund (``charge.refunded``) or a dispute (``charge.dispute.created``) takes the
    unspent credits back and ends the plan; the subscription is then cancelled at Stripe
    (after the database transaction, because that is a network call) so it cannot bill
    again. A partial refund is left to a person in the admin console.
    """
    etype, event_id = event.get("type", ""), event.get("id", "")
    reversal = _REVERSALS.get(etype)
    handler = _HANDLERS.get(etype)
    if (handler is None and reversal is None) or not event_id:
        return "ignored"
    later: list = []
    obj = (event.get("data") or {}).get("object") or {}
    with db.write_connection() as conn:
        if not service.claim_event(conn, PROVIDER, event_id, etype):
            return "duplicate"
        result = reversal(conn, obj, later) if reversal else handler(conn, obj)
    for sub_id in later:
        try:
            cancel_subscription(sub_id)
        except StripeError as e:                   # the admin console shows the leftover
            log.error("could not cancel Stripe subscription %s after a reversal: %s", sub_id, e)
    return result
