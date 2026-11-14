"""Operator commands that need no web session.

    python -m studio.manage verify you@example.com   mark an email as verified
    python -m studio.manage users                    list accounts
    python -m studio.manage payos-webhook <url>      register the PayOS webhook URL

``verify`` exists for the first admin on a machine with no SMTP configured: an admin
must have a verified email (see ``auth.User.is_admin``), and nothing can send the
confirmation link yet.
"""

import sys

from . import db


def main(argv) -> int:
    if len(argv) >= 2 and argv[0] == "verify":
        email = argv[1].strip().lower()
        with db.connection() as conn:
            cur = conn.execute("UPDATE users SET email_verified_at = COALESCE(email_verified_at, ?) "
                               "WHERE email = ?", (db.now(), email))
        print("verified" if cur.rowcount else f"no account with email {email}")
        return 0 if cur.rowcount else 1
    if argv and argv[0] == "users":
        with db.connection() as conn:
            for r in conn.execute("SELECT id, email, plan, email_verified_at, disabled_at FROM users ORDER BY id"):
                flags = ("verified " if r["email_verified_at"] else "") + ("DISABLED" if r["disabled_at"] else "")
                print(f"{r['id']:>5}  {r['email']:<40} {r['plan']:<8} {flags}".rstrip())
        return 0
    if len(argv) >= 2 and argv[0] == "payos-webhook":
        from .payments import payos_provider
        if not payos_provider.configured():
            print("Set PAYOS_CLIENT_ID, PAYOS_API_KEY and PAYOS_CHECKSUM_KEY first.")
            return 1
        # PayOS posts a signed test notification to the URL before accepting it, so the
        # server behind the URL must already be running with the same checksum key.
        print(payos_provider.register_webhook(argv[1].strip()))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
