"""First-run checklist shown on the projects page.

Most steps are *derived* from data that already exists, so they can never drift from
reality (a deleted brand kit un-ticks its step, an unverified address stays unticked):
verified email, a brand kit, a first project. Only what the server cannot see is stored
(``onboarding`` table): the pricing page was opened, a social network was connected (the
Upload-Post key lives in the browser, so the dashboard reports it once), and the person
closed the checklist.
"""

from typing import Optional

from . import db, mailer

# Steps the dashboard may report itself. Anything else is derived, never client-settable.
REPORTABLE = {"pricing": "pricing_seen_at", "social": "social_connected_at"}
_COLUMNS = ("pricing_seen_at", "social_connected_at", "dismissed_at")


class OnboardingError(Exception):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def _touch(conn, user_id: int, column: str, value: Optional[float]) -> None:
    """Set one column the first time only, creating the row on first write."""
    if column not in _COLUMNS:       # never user input, but this goes into SQL text
        raise ValueError(column)
    now = db.now()
    conn.execute("INSERT OR IGNORE INTO onboarding (user_id, updated_at) VALUES (?, ?)", (user_id, now))
    conn.execute(f"UPDATE onboarding SET {column} = COALESCE({column}, ?), updated_at = ? WHERE user_id = ?",
                 (value, now, user_id))


def status(user_id: int) -> dict:
    with db.connection() as conn:
        user = conn.execute("SELECT email_verified_at FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise OnboardingError("not_found", "Account not found.", 404)
        kits = conn.execute("SELECT COUNT(*) FROM brand_kits WHERE user_id = ?", (user_id,)).fetchone()[0]
        projects = conn.execute("SELECT COUNT(*) FROM projects WHERE user_id = ? "
                                "AND status NOT IN ('failed', 'cancelled')", (user_id,)).fetchone()[0]
        mine = conn.execute("SELECT * FROM onboarding WHERE user_id = ?", (user_id,)).fetchone()
    steps = []
    # Without a mail server nobody can verify an address, so the step would be a dead end.
    if mailer.verification_required():
        steps.append({"id": "verify_email", "done": user["email_verified_at"] is not None})
    steps += [
        {"id": "brand_kit", "done": kits > 0},
        {"id": "first_clip", "done": projects > 0},
        {"id": "social", "done": bool(mine and mine["social_connected_at"])},
        {"id": "pricing", "done": bool(mine and mine["pricing_seen_at"])},
    ]
    done = sum(1 for s in steps if s["done"])
    return {
        "steps": steps, "done": done, "total": len(steps),
        "complete": done == len(steps),
        "dismissed": bool(mine and mine["dismissed_at"]),
    }


def report(user_id: int, step: str) -> dict:
    column = REPORTABLE.get(step)
    if column is None:
        raise OnboardingError("unknown_step", "That step is not reported by the client.")
    with db.write_connection() as conn:
        _touch(conn, user_id, column, db.now())
    return status(user_id)


def dismiss(user_id: int) -> dict:
    with db.write_connection() as conn:
        _touch(conn, user_id, "dismissed_at", db.now())
    return status(user_id)
