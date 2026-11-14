"""Paying for ViralShorts: plans, credit packs and the two payment providers.

    service.py          provider-neutral rules (plans, grants, idempotency, history)
    stripe_provider.py  card payments: Checkout, Customer Portal, signed webhooks
    payos_provider.py   Vietnamese bank transfer / VietQR through PayOS, signed webhooks
    api.py              the FastAPI router (/api/billing/*, /api/stripe/webhook, /api/payos/webhook)

Written for this project and independent of ``cloud/``, whose licence does not allow
a paid service to be built on it.
"""

import os


def frontend_url() -> str:
    """Where the browser returns after paying. FRONTEND_URL, else STUDIO_FRONTEND_URL,
    else the local dev dashboard."""
    return (os.environ.get("FRONTEND_URL") or os.environ.get("STUDIO_FRONTEND_URL")
            or "http://localhost:5175").rstrip("/")


def enabled_providers() -> list:
    """The providers whose credentials are configured, in the order to offer them."""
    from . import payos_provider, stripe_provider
    out = []
    if stripe_provider.configured():
        out.append("stripe")
    if payos_provider.configured():
        out.append("payos")
    return out
