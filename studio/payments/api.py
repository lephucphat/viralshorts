"""HTTP surface of billing: plans, checkout, status, and the two provider webhooks."""

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import auth, credits, db, lifecycle, plans, promo, usage
from ..api import current_user
from . import enabled_providers, payos_provider, service, stripe_provider


class SyncBody(BaseModel):
    order: str


class CheckoutBody(BaseModel):
    kind: str                 # "subscription" | "topup"
    item: str                 # plan id or pack id
    provider: Optional[str] = None


class BillingInfoBody(BaseModel):
    company: str = ""
    tax_code: str = ""
    address: str = ""
    email: str = ""


class RedeemBody(BaseModel):
    code: str


def _seller() -> dict:
    """The business on the receipt. Set in the environment; blank means 'not filled in yet'."""
    return {k: os.environ.get(env, "") for k, env in (
        ("name", "COMPANY_NAME"), ("tax_code", "COMPANY_TAX_CODE"),
        ("address", "COMPANY_ADDRESS"), ("email", "SUPPORT_EMAIL"))}


def _fail(status: int, code: str, message: str):
    return HTTPException(status_code=status, detail={"error": code, "message": message})


def _bad_signature(request: Request):
    """The error for an unsigned or forged webhook. A caller that keeps sending them is
    guessing: slow it down (a real provider never sends a bad signature for long)."""
    ip = request.client.host if request.client else ""
    try:
        auth.throttle(f"webhook-bad:{ip}", 60, 600)
    except auth.AuthError:
        return _fail(429, "too_many_attempts", "Too many invalid requests.")
    return _fail(400, "bad_signature", "Invalid signature.")


def _customer_id(user_id: int, provider: str) -> Optional[str]:
    with db.connection() as conn:
        row = conn.execute("SELECT payment_customer_id FROM users WHERE id = ?", (user_id,)).fetchone()
    ref = (row["payment_customer_id"] if row else None) or ""
    prefix = provider + ":"
    return ref[len(prefix):] if ref.startswith(prefix) else None


def build_router() -> APIRouter:
    router = APIRouter()

    @router.get("/api/billing/plans")
    def list_plans():
        """What can be bought. Public: the pricing page shows it before sign-in."""
        return {
            "plans": [p.public() for p in plans.PLANS.values()],
            "packs": [p.public() for p in plans.PACKS.values()],
            "costs": plans.COSTS,
            "providers": enabled_providers(),
            "contact_plans": [plans.BUSINESS_CONTACT],
            "prices_placeholder": plans.prices_are_placeholder(),
            "yearly_checkout": plans.yearly_billing_enabled(),
        }

    @router.get("/api/billing/status")
    def status(user: auth.User = Depends(current_user)):
        service.expire_due_subscriptions()
        plan_id = usage.summary(user.id)["plan"]
        sub = service.active_subscription(user.id)
        return {
            "plan": plans.get_plan(plan_id).public(),
            "subscription": ({
                "provider": sub["provider"], "status": sub["status"],
                "current_period_end": sub["current_period_end"],
                "cancel_at_period_end": bool(sub["cancel_at_period_end"]),
            } if sub else None),
            "usage": usage.summary(user.id),
            "payments": service.payments_for_user(user.id),
            "providers": enabled_providers(),
        }

    @router.post("/api/billing/checkout")
    def checkout(body: CheckoutBody, user: auth.User = Depends(current_user)):
        available = enabled_providers()
        if not available:
            raise _fail(503, "payments_off", "Payments are not configured on this server yet.")
        provider = body.provider or available[0]
        if provider not in available:
            raise _fail(400, "bad_provider", "That payment method is not available.")
        if body.kind not in ("subscription", "topup"):
            raise _fail(400, "bad_kind", "Unknown purchase type.")
        if body.kind == "subscription":
            conflict = service.subscription_conflict(user.id, provider, body.item)
            if conflict:
                raise _fail(409, conflict[0], conflict[1])
        try:
            if provider == "stripe":
                result = stripe_provider.create_checkout(
                    user.id, user.email, body.kind, body.item, _customer_id(user.id, "stripe"))
            else:
                result = payos_provider.create_payment(user.id, body.kind, body.item)
        except (stripe_provider.StripeError, payos_provider.PayOSError) as e:
            raise _fail(getattr(e, "status", 502), "checkout_failed", str(e))
        return {"provider": provider, **result}

    @router.post("/api/billing/payos/sync")
    def payos_sync(body: SyncBody, user: auth.User = Depends(current_user)):
        """After the PayOS page sends the customer back: confirm the order with PayOS now
        instead of waiting for (or without) a webhook."""
        try:
            result = payos_provider.sync_order(user.id, body.order)
        except payos_provider.PayOSError as e:
            raise _fail(e.status, "sync_failed", str(e))
        if result == "applied":
            lifecycle.background(lifecycle.send_pending_receipts)
        return {"result": result}

    @router.post("/api/billing/portal")
    def portal(user: auth.User = Depends(current_user)):
        customer = _customer_id(user.id, "stripe")
        if not customer or not stripe_provider.configured():
            raise _fail(404, "no_portal", "There is no card subscription to manage.")
        try:
            return {"url": stripe_provider.create_portal(customer)}
        except stripe_provider.StripeError as e:
            raise _fail(e.status, "portal_failed", str(e))

    # ---- plan lifecycle -------------------------------------------------------------------
    def _set_cancel(user: auth.User, cancel: bool):
        refs = service.live_subscription_refs(user.id, "stripe")
        if not refs or not stripe_provider.configured():
            raise _fail(404, "no_card_subscription", "There is no card subscription to change.")
        try:
            for ref in refs:
                stripe_provider.set_cancel_at_period_end(ref, cancel)
        except stripe_provider.StripeError as e:
            raise _fail(502, "cancel_failed", str(e))
        service.set_cancel_flag(user.id, cancel)
        return {"cancel_at_period_end": cancel}

    @router.post("/api/billing/cancel")
    def cancel(user: auth.User = Depends(current_user)):
        """Stop a card subscription from renewing; the plan runs to the end of the paid period."""
        return _set_cancel(user, True)

    @router.post("/api/billing/resume")
    def resume(user: auth.User = Depends(current_user)):
        return _set_cancel(user, False)

    # ---- receipts, invoice details ----------------------------------------------------------
    @router.get("/api/billing/info")
    def get_info(user: auth.User = Depends(current_user)):
        return service.get_billing_info(user.id)

    @router.put("/api/billing/info")
    def put_info(body: BillingInfoBody, user: auth.User = Depends(current_user)):
        try:
            return service.save_billing_info(user.id, body.company, body.tax_code, body.address, body.email)
        except service.BillingInfoError as e:
            raise _fail(e.status, e.code, e.message)

    @router.get("/api/billing/payments/{payment_id}")
    def receipt(payment_id: int, user: auth.User = Depends(current_user)):
        """Everything a printable receipt needs: the payment, who pays, who is paid."""
        payment = service.payment_for_user(user.id, payment_id)
        if payment is None:
            raise _fail(404, "not_found", "No such payment.")
        return {
            "payment": payment,
            "buyer": {**service.get_billing_info(user.id), "name": user.name, "account_email": user.email},
            "seller": _seller(),
        }

    @router.post("/api/billing/payments/{payment_id}/invoice")
    def invoice(payment_id: int, user: auth.User = Depends(current_user)):
        try:
            return service.request_invoice(user.id, payment_id)
        except service.BillingInfoError as e:
            raise _fail(e.status, e.code, e.message)

    @router.post("/api/billing/redeem")
    def redeem(body: RedeemBody, user: auth.User = Depends(current_user)):
        try:
            granted = promo.redeem(user.id, body.code)
        except promo.PromoError as e:
            raise _fail(e.status, e.code, e.message)
        except auth.AuthError as e:                      # throttled
            raise _fail(429, getattr(e, "code", "too_many_attempts"), str(e))
        return {"credits": granted, "usage": usage.summary(user.id)}

    # ---- webhooks: authenticated by signature, never by a session -----------------------
    @router.post("/api/stripe/webhook")
    async def stripe_webhook(request: Request):
        payload = await request.body()
        try:
            event = stripe_provider.verify_webhook(payload, request.headers.get("stripe-signature", ""))
        except stripe_provider.SignatureError:
            raise _bad_signature(request)
        try:
            result = stripe_provider.handle_event(event)
        except service.UnknownUser:
            # The event that links this one to an account has not arrived yet: ask
            # Stripe to retry (it backs off for days) rather than lose the credits.
            raise _fail(503, "retry_later", "Account not linked yet.")
        if result == "applied":
            lifecycle.background(lifecycle.send_pending_receipts)
        lifecycle.background(lifecycle.send_billing_notices)
        return {"received": True, "result": result}

    @router.post("/api/payos/webhook")
    async def payos_webhook(request: Request):
        try:
            body = await request.json()
        except ValueError:
            raise _fail(400, "bad_json", "Invalid body.")
        try:
            result = payos_provider.handle_webhook(body)
        except payos_provider.SignatureError:
            raise _bad_signature(request)
        if result == "applied":
            lifecycle.background(lifecycle.send_pending_receipts)
        return {"success": True, "result": result}

    return router
