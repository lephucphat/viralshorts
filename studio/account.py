"""Everything an account holds, as one downloadable JSON file ("export my data").

Covers the profile, projects (metadata, not the video files: those are downloaded from each
project), brand kits, credits and payments. Secrets never appear: no password hash, no
session or API key material, no payment-provider tokens.
"""

import time
from typing import Optional

from . import db, plans, schedule


def _rows(conn, sql: str, *args) -> list:
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def export_data(user_id: int) -> Optional[dict]:
    with db.connection() as conn:
        u = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if u is None:
            return None
        profile = {
            "id": u["id"], "email": u["email"], "name": u["name"], "language": u["lang"], "plan": u["plan"],
            "created_at": u["created_at"], "last_login_at": u["last_login_at"],
            "email_verified_at": u["email_verified_at"], "signed_in_with_google": bool(u["google_sub"]),
            "terms_accepted_at": u["tos_accepted_at"], "terms_version": u["tos_version"],
        }
        data = {
            "exported_at": time.time(),
            "profile": profile,
            "projects": _rows(
                conn, "SELECT job_id, title, source_kind, source_ref, status, duration_seconds, clip_count, "
                      "top_score, created_at, finished_at, archived_at, archive_expires_at FROM projects "
                      "WHERE user_id = ? ORDER BY created_at DESC", user_id),
            "brand_kits": _rows(
                conn, "SELECT name, logo_position, logo_opacity, logo_scale, primary_color, secondary_color, "
                      "caption_preset, hook_style, layout, output_format, is_default, created_at "
                      "FROM brand_kits WHERE user_id = ?", user_id),
            "subscriptions": _rows(
                conn, "SELECT provider, plan, status, current_period_start, current_period_end, "
                      "cancel_at_period_end, created_at FROM subscriptions WHERE user_id = ?", user_id),
            "payments": _rows(
                conn, "SELECT provider, kind, item, amount, currency, credits, status, created_at, paid_at "
                      "FROM payments WHERE user_id = ? ORDER BY created_at DESC", user_id),
            "credit_grants": _rows(
                conn, "SELECT kind, amount, remaining, expires_at, created_at FROM credit_grants "
                      "WHERE user_id = ? ORDER BY id", user_id),
            "credit_ledger": _rows(
                conn, "SELECT kind, ref, credits, status, created_at FROM credit_ledger "
                      "WHERE user_id = ? ORDER BY id", user_id),
            "scheduled_posts": schedule.export_rows(conn, user_id),
            "api_keys": _rows(
                conn, "SELECT name, prefix, created_at, last_used_at, revoked_at FROM api_keys "
                      "WHERE user_id = ?", user_id),
        }
    data["credits_now"] = None
    if plans.paid_mode():
        from . import credits
        data["credits_now"] = credits.balance(user_id)
    return data
