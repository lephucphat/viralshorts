"""Operators (verified ADMIN_EMAILS) are not metered; everyone else still is."""
import pytest

from studio import auth, credits, db, usage


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_DB_PATH", str(tmp_path / "studio.db"))
    monkeypatch.setenv("STUDIO_SECRET", "test-secret")
    monkeypatch.setenv("STUDIO_PAID", "1")
    monkeypatch.setenv("ADMIN_EMAILS", "boss@example.com")
    monkeypatch.delenv("ADMIN_UNLIMITED", raising=False)
    monkeypatch.delenv("DAILY_AI_BUDGET_CREDITS", raising=False)
    db._initialised_for = None
    auth.clear_all_throttles()
    db.init()
    yield


def _user(email, verified=True):
    u = auth.register(email, "correct horse", "X")
    if verified:
        with db.connection() as c:
            c.execute("UPDATE users SET email_verified_at = ? WHERE id = ?", (db.now(), u.id))
    return u


def _empty_wallet(uid):
    credits.balance(uid)          # the free grant is lazy: create it first, then drain it
    with db.connection() as c:
        c.execute("UPDATE credit_grants SET remaining = 0 WHERE user_id = ?", (uid,))


def test_admin_can_reserve_with_zero_balance():
    u = _user("boss@example.com")
    _empty_wallet(u.id)
    assert credits.balance(u.id)["remaining"] == 0
    credits.can_afford(u.id, 50)
    lid = credits.reserve(u.id, "j1", "process", 50)
    assert credits.commit(lid, actual=80) == 80
    assert credits.balance(u.id)["remaining"] == 0
    assert credits.spend_up_to(u.id, "j2", "dubbing", 5) == 5
    assert usage.summary(u.id)["unlimited"] is True


def test_admin_is_not_blocked_by_daily_budget(monkeypatch):
    monkeypatch.setenv("DAILY_AI_BUDGET_CREDITS", "1")
    u = _user("boss@example.com")
    credits.reserve(u.id, "j1", "thumbnails", 20, budgeted=True)


def test_regular_user_is_still_metered():
    u = _user("someone@example.com")
    _empty_wallet(u.id)
    with pytest.raises(credits.QuotaError):
        credits.reserve(u.id, "j1", "process", 2)
    assert usage.summary(u.id)["unlimited"] is False


def test_unverified_admin_address_is_not_unlimited():
    u = _user("boss@example.com", verified=False)
    assert credits.is_unlimited(u.id) is False


def test_switch_off(monkeypatch):
    monkeypatch.setenv("ADMIN_UNLIMITED", "0")
    u = _user("boss@example.com")
    _empty_wallet(u.id)
    with pytest.raises(credits.QuotaError):
        credits.reserve(u.id, "j1", "process", 2)
