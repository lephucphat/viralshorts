"""Plan catalogue, credit costs and top-up packs for the paid edition.

Everything the business decides about money lives in this one file, so changing
a price or a limit never touches the billing code. **The numbers below are
placeholders** chosen so the arithmetic works; set the real ones before selling
anything (see ``docs/pricing.md`` for how to derive them from the API costs).

Currency model
--------------
One internal unit, the *credit*. One minute of source video processed by the
clip generator costs one credit (that is what the old minutes allowance
meant), so existing accounts keep their meaning. The other features cost more
because they spend the operator's money on third-party APIs.

Prices are integers in the *minor unit* of the currency: US cents for Stripe,
whole dong for PayOS (VND has no minor unit).
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    credits: int                  # credits granted every billing period
    max_active_jobs: int          # projects processing at once
    priority: int                 # queue priority, LOWER runs first
    retention_days: int           # how long finished clips are kept
    features: frozenset = field(default_factory=frozenset)
    price_usd_cents: int = 0      # per month, Stripe
    price_vnd: int = 0            # per month, PayOS
    yearly_discount_months: int = 2   # a yearly plan is billed as 12 - this

    @property
    def price_usd_cents_yearly(self) -> int:
        """Total for one year paid up front: 12 months minus the discount months."""
        return self.price_usd_cents * max(0, 12 - self.yearly_discount_months)

    @property
    def price_vnd_yearly(self) -> int:
        return self.price_vnd * max(0, 12 - self.yearly_discount_months)

    def public(self) -> dict:
        return {
            "id": self.id, "name": self.name, "credits": self.credits,
            "max_active_jobs": self.max_active_jobs,
            "retention_days": self.retention_days,
            "features": sorted(self.features),
            "price_usd_cents": self.price_usd_cents, "price_vnd": self.price_vnd,
            "price_usd_cents_yearly": self.price_usd_cents_yearly,
            "price_vnd_yearly": self.price_vnd_yearly,
            "yearly_discount_months": self.yearly_discount_months,
        }


# Feature flags a plan can switch on. The clip generator and thumbnails are in
# every plan; the features that call expensive third-party APIs are not.
CORE = frozenset({"clips", "subtitles", "hooks", "thumbnails"})
PAID = CORE | {"dubbing", "publish", "effects"}
FULL = PAID | {"ai_shorts", "api_access"}

PLANS: Dict[str, Plan] = {
    "free": Plan("free", "Miễn phí", credits=30, max_active_jobs=1, priority=3,
                 retention_days=1, features=CORE),
    "starter": Plan("starter", "Starter", credits=300, max_active_jobs=2, priority=2,
                    retention_days=14, features=PAID,
                    price_usd_cents=1200, price_vnd=299_000),
    "pro": Plan("pro", "Pro", credits=1200, max_active_jobs=3, priority=1,
                retention_days=60, features=FULL,
                price_usd_cents=3900, price_vnd=999_000),
}
DEFAULT_PLAN = "free"

# A plan nobody can buy online: the pricing page shows it as "contact us". It is NOT in
# PLANS on purpose (nothing may check out, grant credits or rank against it); the numbers
# are what a sales conversation starts from, and they are placeholders like the rest.
BUSINESS_CONTACT = {
    "id": "business", "name": "Business", "contact": True,
    "credits": 5000, "max_active_jobs": 10, "retention_days": 180,
    "features": sorted(FULL | {"brand_kits", "priority_support"}),
}

def prices_are_placeholder() -> bool:
    """True until the operator has set the real numbers above. The pricing page prints a
    visible notice while this holds so nobody mistakes a development price for an offer.
    Set ``STUDIO_PRICES_FINAL=1`` once ``PLANS`` and ``PACKS`` carry the real prices."""
    return os.environ.get("STUDIO_PRICES_FINAL", "").lower() not in ("1", "true", "yes")


def yearly_billing_enabled() -> bool:
    """Whether checkout can bill a yearly plan. The providers only create monthly
    subscriptions today, so the yearly price is shown but not purchasable until
    ``STUDIO_YEARLY_BILLING=1`` is set together with the provider-side yearly prices."""
    return os.environ.get("STUDIO_YEARLY_BILLING", "").lower() in ("1", "true", "yes")


# A job that starts from a URL is only measured after it is downloaded, so this many
# credits must be available to start one; the real length is settled at the end.
MIN_URL_JOB_CREDITS = 10


def get_plan(plan_id: Optional[str]) -> Plan:
    return PLANS.get(plan_id or DEFAULT_PLAN, PLANS[DEFAULT_PLAN])


def paid_plans() -> Dict[str, Plan]:
    return {k: v for k, v in PLANS.items() if v.price_usd_cents or v.price_vnd}


def has_feature(plan_id: Optional[str], feature: str) -> bool:
    return feature in get_plan(plan_id).features


# --- what each action costs, in credits ------------------------------------------------
# "per_minute" entries are multiplied by the minutes of the source or clip.
COSTS = {
    "process_per_minute": 1,      # clip generator, per source minute
    "analysis": 1,
    "hook": 1,
    "render": 3,
    "transcribe": 2,
    "subtitles": 2,
    "thumbnails": 3,              # one generation of a thumbnail set
    "dubbing_per_minute": 4,      # ElevenLabs dubbing, per minute of video
    "ai_actor_options": 2,        # one fal.ai actor image (a request asks for several)
    "ai_short_low": 25,           # Hailuo + lip-sync, ~0.8 USD of API cost
    "ai_short_premium": 60,       # Kling avatar, ~2 USD of API cost
}


# --- what the third-party APIs cost us, per credit spent (USD) ---------------------------
# ESTIMATES from the providers' public prices at the time of writing, so the admin console
# can show a margin. They are NOT read from any invoice: replace them with the real numbers
# once there are a few weeks of bills, or override without a deploy with
# ``AI_COST_RATES="dubbing=0.05,thumbnail=0.03"``. A ledger kind that contains the key uses
# its rate; the first match in this order wins.
COST_USD_PER_CREDIT = (
    ("saasshorts", 0.033),        # fal.ai Hailuo / Kling: ~0.8 USD per 25 credits, ~2 USD per 60
    ("dubbing", 0.04),            # ElevenLabs dubbing
    ("thumbnail", 0.03),          # Gemini image generation
    ("process", 0.006),           # Gemini video analysis + server CPU (Whisper) per source minute
)
DEFAULT_COST_USD_PER_CREDIT = 0.004   # Gemini text calls (analysis, hooks, subtitles) and renders


def cost_rate_usd(kind: str) -> float:
    """Estimated USD of provider cost behind one credit spent on ``kind``."""
    kind = (kind or "").lower()
    for pair in os.environ.get("AI_COST_RATES", "").split(","):
        key, _, value = pair.partition("=")
        if key.strip() and key.strip().lower() in kind:
            try:
                return max(0.0, float(value))
            except ValueError:
                pass
    for key, rate in COST_USD_PER_CREDIT:
        if key in kind:
            return rate
    return DEFAULT_COST_USD_PER_CREDIT


def estimated_cost_usd(kind: str, credits: int) -> float:
    return round(max(0, int(credits)) * cost_rate_usd(kind), 6)


def cost(name: str, minutes: float = 1) -> int:
    """Credits for one action. Per-minute actions round the minutes up."""
    if name not in COSTS:
        raise KeyError(f"unknown cost {name!r}")
    base = COSTS[name]
    if name.endswith("_per_minute"):
        return base * max(1, int(-(-float(minutes) // 1)))
    return base


# --- one-off credit packs ---------------------------------------------------------------
@dataclass(frozen=True)
class Pack:
    id: str
    credits: int
    price_usd_cents: int
    price_vnd: int

    def public(self) -> dict:
        return {"id": self.id, "credits": self.credits,
                "price_usd_cents": self.price_usd_cents, "price_vnd": self.price_vnd}


PACKS: Dict[str, Pack] = {
    "topup_100": Pack("topup_100", 100, 500, 129_000),
    "topup_500": Pack("topup_500", 500, 2000, 499_000),
}


def get_pack(pack_id: str) -> Optional[Pack]:
    return PACKS.get(pack_id)


def archive_days(plan_id: Optional[str]) -> int:
    """How many days a finished project is kept in object storage for this plan, 0 for none.

    A plan whose retention is a single day is already served by the server's own working
    folder (swept after about a day), so it is not copied: archiving is the paid benefit."""
    days = get_plan(plan_id).retention_days
    return days if days > 1 else 0


# --- switches -------------------------------------------------------------------------------
def paid_mode() -> bool:
    """True when credits, plans and payments are in force.

    Off by default so local development and the free self-hosted flavour keep
    the simple monthly-minutes allowance. Read per call so tests can flip it.
    """
    return os.environ.get("STUDIO_PAID", "").lower() in ("1", "true", "yes")


def daily_ai_budget_credits() -> int:
    """Hard ceiling of credits the whole site may spend on API-backed features
    per UTC day (0 = no ceiling). A runaway loop or an abusive account then
    stops at a bounded cost instead of at the end of the API balance."""
    try:
        return max(0, int(os.environ.get("DAILY_AI_BUDGET_CREDITS", "0")))
    except ValueError:
        return 0
