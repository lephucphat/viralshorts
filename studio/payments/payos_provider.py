"""Vietnamese bank transfer / VietQR through PayOS (https://payos.vn).

PayOS has no automatic renewal: each plan purchase pays for one 30-day period and
the customer pays again to continue. That is the usual model for Vietnamese
payment pages and it is what ``studio/payments/service.py`` is built to handle.

    PAYOS_CLIENT_ID       x-client-id
    PAYOS_API_KEY         x-api-key
    PAYOS_CHECKSUM_KEY    key used to sign requests and verify webhooks

The request/webhook signing follows PayOS's published scheme (HMAC-SHA256 over
alphabetically ordered ``key=value`` pairs) and reproduces the documented sample
webhook signature exactly (tests/test_studio_payments.py). It has NOT been exercised
against the live PayOS sandbox from this repository: run one sandbox payment end to end
before relying on it (see docs/payments.md).
"""

import hashlib
import hmac
import os
import random
import time
from typing import Optional

import httpx

from .. import db, plans
from . import frontend_url, service

API = "https://api-merchant.payos.vn"
PROVIDER = "payos"
PERIOD_SECONDS = 30 * 24 * 3600


class PayOSError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


class SignatureError(Exception):
    pass


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def configured() -> bool:
    return bool(_env("PAYOS_CLIENT_ID") and _env("PAYOS_API_KEY") and _env("PAYOS_CHECKSUM_KEY"))


# ---- signing ---------------------------------------------------------------------------------
def _sign(message: str, key: Optional[str] = None) -> str:
    return hmac.new((key or _env("PAYOS_CHECKSUM_KEY")).encode(), message.encode(),
                    hashlib.sha256).hexdigest()


def data_signature(data: dict, key: Optional[str] = None) -> str:
    """Signature of a webhook ``data`` object: every field, sorted by name, as
    ``name=value`` joined with ``&`` (``None`` becomes an empty value)."""
    def text(v):
        if v is None or v == "null" or v == "undefined":
            return ""
        return str(v)
    message = "&".join(f"{k}={text(data[k])}" for k in sorted(data))
    return _sign(message, key)


def request_signature(amount: int, cancel_url: str, description: str, order_code: int,
                      return_url: str, key: Optional[str] = None) -> str:
    return _sign(f"amount={amount}&cancelUrl={cancel_url}&description={description}"
                 f"&orderCode={order_code}&returnUrl={return_url}", key)


def verify_webhook(body: dict, key: Optional[str] = None) -> dict:
    """The webhook's ``data`` if the signature matches, else SignatureError."""
    data, signature = body.get("data"), body.get("signature")
    if not isinstance(data, dict) or not signature:
        raise SignatureError("missing data or signature")
    if not (key or _env("PAYOS_CHECKSUM_KEY")):
        raise SignatureError("checksum key not configured")
    if not hmac.compare_digest(data_signature(data, key), str(signature)):
        raise SignatureError("signature mismatch")
    return data


# ---- creating payments -----------------------------------------------------------------------
def _headers() -> dict:
    return {"x-client-id": _env("PAYOS_CLIENT_ID"), "x-api-key": _env("PAYOS_API_KEY")}


def new_order_code() -> int:
    """PayOS needs a unique integer (JS safe range, under 2**53). Milliseconds since the epoch
    (13 digits) plus two random digits: 15 digits, far below the limit, and two orders in the
    same second do not collide."""
    return int(time.time() * 1000) * 100 + random.randint(0, 99)


def create_payment(user_id: int, kind: str, item: str) -> dict:
    """A PayOS payment link for a plan period (``subscription``) or credit pack (``topup``).

    A ``pending`` payment row is written first: the webhook identifies the buyer by the
    order code, never by anything the browser sends back.
    """
    if not configured():
        raise PayOSError("PayOS is not configured.", 503)
    if kind == "subscription":
        plan = plans.PLANS.get(item)
        if plan is None or not plan.price_vnd:
            raise PayOSError("Unknown plan.", 400)
        amount, name, granted = plan.price_vnd, f"ViralShorts {plan.name} (30 ngày)", plan.credits
    elif kind == "topup":
        pack = plans.get_pack(item)
        if pack is None:
            raise PayOSError("Unknown credit pack.", 400)
        amount, name, granted = pack.price_vnd, f"ViralShorts {pack.credits} credit", pack.credits
    else:
        raise PayOSError("Unknown purchase type.", 400)

    code = new_order_code()
    # 9 characters is the limit for a bank account not linked through PayOS; the order is
    # identified by orderCode, never by this text, so it only has to be short and recognisable.
    description = f"VS{code % 10**6:06d}"
    base = frontend_url()
    return_url = f"{base}/#/account?checkout=success&order={code}"
    cancel_url = f"{base}/#/pricing?checkout=cancelled"
    body = {
        "orderCode": code, "amount": amount, "description": description,
        "items": [{"name": name, "quantity": 1, "price": amount}],
        "returnUrl": return_url, "cancelUrl": cancel_url,
        "signature": request_signature(amount, cancel_url, description, code, return_url),
    }
    with db.write_connection() as conn:
        service.record_payment(conn, user_id, PROVIDER, str(code), kind, item, amount, "vnd",
                               granted, "pending")
    try:
        resp = httpx.post(f"{API}/v2/payment-requests", json=body, headers=_headers(), timeout=30.0)
        payload = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        raise PayOSError(f"Could not reach PayOS: {e}")
    if resp.status_code >= 400 or payload.get("code") != "00" or not payload.get("data"):
        raise PayOSError(payload.get("desc") or "PayOS rejected the request.")
    return {"id": str(code), "url": payload["data"]["checkoutUrl"]}


def register_webhook(url: str) -> dict:
    """Tell PayOS where to send payment notifications (run once per deployment)."""
    resp = httpx.post(f"{API}/confirm-webhook", json={"webhookUrl": url},
                      headers=_headers(), timeout=30.0)
    return resp.json()


# ---- applying a paid order -------------------------------------------------------------------
def handle_webhook(body: dict) -> str:
    """Apply a PayOS payment notification. Returns ``applied``, ``duplicate`` or ``ignored``.

    Raises SignatureError for a forged or corrupted notification.
    """
    data = verify_webhook(body)
    code = str(data.get("orderCode", ""))
    paid = bool(body.get("success", body.get("code") == "00")) and str(data.get("code", "00")) == "00"
    with db.write_connection() as conn:
        row = conn.execute("SELECT * FROM payments WHERE provider = ? AND provider_ref = ?",
                           (PROVIDER, code)).fetchone()
        if row is None:
            return "ignored"                       # PayOS's own webhook test, or someone else's order
        if not paid:
            return "ignored"
        if int(data.get("amount", -1)) != int(row["amount"]):
            return "ignored"                       # never grant for an amount we did not ask for
        return _apply_paid(conn, row, code)


def _apply_paid(conn, row, code: str) -> str:
    """Grant what a paid order bought. Shared by the webhook and the API reconciliation, and
    idempotent across both through the ``payment_events`` claim."""
    if not service.claim_event(conn, PROVIDER, f"order:{code}", "payment.paid"):
        return "duplicate"
    user_id, kind, item = int(row["user_id"]), row["kind"], row["item"]
    now = db.now()
    if kind == "subscription":
        plan = plans.get_plan(item)
        # Paying again before the period ends queues the next period behind it.
        latest = conn.execute(
            "SELECT MAX(current_period_end) AS e FROM subscriptions WHERE user_id = ? "
            "AND provider = ? AND status = 'active' AND plan = ?",
            (user_id, PROVIDER, plan.id)).fetchone()["e"]
        start = max(now, latest or 0)
        end = start + PERIOD_SECONDS
        service.upsert_subscription(conn, user_id, PROVIDER, f"order:{code}", plan.id,
                                    "active", start, end)
        service.grant_period_credits(conn, user_id, plan.id, f"payos:order:{code}", end)
        service.refresh_user_plan(conn, user_id)
        granted = plan.credits
    else:
        granted = service.grant_topup(conn, user_id, item, f"payos:order:{code}")
    service.record_payment(conn, user_id, PROVIDER, code, kind, item, int(row["amount"]),
                           "vnd", granted, "paid", now)
    return "applied"


# ---- reconciliation: ask PayOS instead of waiting for the webhook ----------------------------
def fetch_status(order_code: str) -> dict:
    """GET /v2/payment-requests/{orderCode}: PayOS's own view of one order."""
    try:
        resp = httpx.get(f"{API}/v2/payment-requests/{order_code}", headers=_headers(), timeout=30.0)
        payload = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        raise PayOSError(f"Could not reach PayOS: {e}")
    if resp.status_code >= 400 or payload.get("code") != "00" or not payload.get("data"):
        raise PayOSError(payload.get("desc") or "PayOS could not find that order.", 404)
    return payload["data"]


def sync_order(user_id: int, order_code: str) -> str:
    """For the page the customer lands on after paying: if PayOS says the order is paid in
    full, apply it now (a webhook that cannot reach a laptop or was delayed does not leave a
    paying customer waiting). Returns ``applied``, ``duplicate``, ``pending`` or ``ignored``.

    Safe by construction: it only ever grants for the caller's own pending order, only when
    PayOS reports status PAID and the full amount, and through the same idempotent claim as
    the webhook. An unknown status string simply grants nothing."""
    if not configured():
        raise PayOSError("PayOS is not configured.", 503)
    code = str(order_code).strip()
    if not code.isdigit():
        return "ignored"
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM payments WHERE provider = ? AND provider_ref = ? AND user_id = ?",
                           (PROVIDER, code, user_id)).fetchone()
    if row is None:
        return "ignored"
    if row["status"] == "paid":
        return "duplicate"
    info = fetch_status(code)
    if str(info.get("status", "")).upper() != "PAID":
        return "pending"
    if int(info.get("amountPaid", info.get("amount", -1)) or -1) < int(row["amount"]):
        return "ignored"
    with db.write_connection() as conn:
        fresh = conn.execute("SELECT * FROM payments WHERE provider = ? AND provider_ref = ?",
                             (PROVIDER, code)).fetchone()
        return _apply_paid(conn, fresh, code)
