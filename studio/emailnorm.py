"""Email normalisation and throwaway-address screening for sign-up.

``canonical`` folds the spellings that all reach one inbox (Gmail ignores dots and
anything after ``+``; other providers ignore ``+tag``), so a person cannot register the
same inbox five times to collect the free credits five times. ``is_disposable`` refuses
well-known throwaway domains; the operator extends the list with ``BLOCKED_EMAIL_DOMAINS``
(comma separated).
"""

import os

_GMAIL = {"gmail.com", "googlemail.com"}

# A short list of the throwaway services seen most often. Not exhaustive on purpose:
# it only has to stop the lazy case, and BLOCKED_EMAIL_DOMAINS adds more without a deploy.
_DISPOSABLE = {
    "mailinator.com", "guerrillamail.com", "guerrillamail.net", "guerrillamail.org", "sharklasers.com",
    "grr.la", "10minutemail.com", "10minutemail.net", "tempmail.com", "temp-mail.org", "temp-mail.io",
    "tempmailo.com", "tempail.com", "throwawaymail.com", "yopmail.com", "yopmail.net", "yopmail.fr",
    "trashmail.com", "trashmail.net", "getnada.com", "nada.email", "maildrop.cc", "dispostable.com",
    "fakeinbox.com", "mailnesia.com", "mintemail.com", "mohmal.com", "emailondeck.com", "burnermail.io",
    "spamgourmet.com", "moakt.com", "mytemp.email", "tmpmail.org", "tmpmail.net", "discard.email",
    "inboxkitten.com", "harakirimail.com", "mail.tm", "dropmail.me", "33mail.com", "anonaddy.me",
    "tempinbox.com", "emailfake.com", "fakemail.net", "mailcatch.com", "spambox.us", "trbvm.com",
}


def _split(email: str):
    local, _, domain = (email or "").strip().lower().rpartition("@")
    return local, domain


def canonical(email: str) -> str:
    """The one spelling shared by every address that lands in the same inbox."""
    local, domain = _split(email)
    if not domain:
        return (email or "").strip().lower()
    local = local.split("+", 1)[0]
    if domain in _GMAIL:
        local = local.replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}"


def _blocked_extra() -> set:
    raw = os.environ.get("BLOCKED_EMAIL_DOMAINS", "")
    return {d.strip().lower() for d in raw.split(",") if d.strip()}


def is_disposable(email: str) -> bool:
    _, domain = _split(email)
    return bool(domain) and (domain in _DISPOSABLE or domain in _blocked_extra())
