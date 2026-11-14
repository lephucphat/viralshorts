"""ViralShorts accounts, project library, brand kits and usage metering.

Standard library only (sqlite3, hashlib.scrypt, hmac): no extra dependency to
install, nothing to configure, and nothing here touches ``cloud/``. It is
switched on with ``ACCOUNTS_ENABLED=1`` (see app.py); with the flag off the app
behaves exactly as the single-user install does.

Layout
    db.py          connection helper + schema migrations
    security.py    password hashing, signed tokens, signed media URLs
    auth.py        registration, login, profile, request -> user
    projects.py    one row per job: the user's library
    brand_kits.py  logo / colours / caption defaults applied to new jobs
    usage.py       monthly minutes allowance
    api.py         the FastAPI router that exposes all of the above
"""

import os


def enabled() -> bool:
    """True when the deployment runs with user accounts."""
    return os.environ.get("ACCOUNTS_ENABLED", "").lower() in ("1", "true", "yes")
