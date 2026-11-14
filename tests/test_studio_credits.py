"""studio/credits.py and plans.py: the paid-edition wallet. Each test gets its own DB."""
import threading

import pytest

from studio import auth, credits, db, plans


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_DB_PATH", str(tmp_path / "studio.db"))
    monkeypatch.setenv("STUDIO_SECRET", "test-secret")
    monkeypatch.delenv("DAILY_AI_BUDGET_CREDITS", raising=False)
    db._initialised_for = None
    auth.clear_all_throttles()
    db.init()
    yield


def _user(email="a@example.com"):
    return auth.register(email, "correct horse", "Ann")


def _balance(uid):
    return credits.balance(uid)["remaining"]


class TestPlans:
    def test_free_plan_is_default_and_unknown_falls_back(self):
        assert plans.get_plan(None).id == "free"
        assert plans.get_plan("nope").id == "free"

    def test_features_gate_the_expensive_things(self):
        assert plans.has_feature("free", "clips")
        assert not plans.has_feature("free", "ai_shorts")
        assert not plans.has_feature("free", "dubbing")
        assert plans.has_feature("pro", "ai_shorts")

    def test_cost_rounds_minutes_up(self):
        assert plans.cost("process_per_minute", 0.2) == 1
        assert plans.cost("dubbing_per_minute", 2.1) == plans.COSTS["dubbing_per_minute"] * 3
        assert plans.cost("thumbnails") == plans.COSTS["thumbnails"]
        with pytest.raises(KeyError):
            plans.cost("nonsense")


class TestFreeGrant:
    def test_new_user_gets_this_months_credits_once(self):
        u = _user()
        free = plans.get_plan("free").credits
        assert _balance(u.id) == free
        assert _balance(u.id) == free          # looking again must not grant again

    def test_paid_user_gets_no_free_grant(self):
        u = _user()
        with db.connection() as c:
            c.execute("UPDATE users SET plan = 'pro' WHERE id = ?", (u.id,))
        assert _balance(u.id) == 0


class TestSpending:
    def test_reserve_commit_charges_and_is_idempotent(self):
        u = _user()
        start = _balance(u.id)
        lid = credits.reserve(u.id, "job1", "process", 10)
        assert _balance(u.id) == start - 10
        assert credits.reserve(u.id, "job1", "process", 10) == lid     # no double charge
        assert _balance(u.id) == start - 10
        assert credits.commit(lid) == 10
        assert _balance(u.id) == start - 10

    def test_release_refunds_everything(self):
        u = _user()
        start = _balance(u.id)
        lid = credits.reserve(u.id, "job1", "process", 12)
        assert credits.release(lid) == 12
        assert _balance(u.id) == start
        assert credits.release(lid) == 0                                # only once

    def test_a_released_job_can_be_reserved_again(self):
        u = _user()
        credits.release(credits.reserve(u.id, "job1", "process", 5))
        credits.reserve(u.id, "job1", "process", 5)
        assert _balance(u.id) == plans.get_plan("free").credits - 5

    def test_insufficient_credits_raises_with_numbers(self):
        u = _user()
        have = _balance(u.id)
        with pytest.raises(credits.QuotaError) as e:
            credits.reserve(u.id, "big", "process", have + 1)
        assert e.value.remaining == have and e.value.required == have + 1
        assert _balance(u.id) == have                                    # nothing was taken

    def test_commit_trues_up_down_and_up(self):
        u = _user()
        start = _balance(u.id)
        a = credits.reserve(u.id, "a", "process", 10)
        assert credits.commit(a, actual=4) == 4
        assert _balance(u.id) == start - 4
        b = credits.reserve(u.id, "b", "process", 3)
        assert credits.commit(b, actual=8) == 8
        assert _balance(u.id) == start - 12

    def test_commit_up_never_fails_when_balance_is_short(self):
        u = _user()
        have = _balance(u.id)
        a = credits.reserve(u.id, "a", "process", have - 1)
        assert credits.commit(a, actual=have + 50) == have       # capped, no exception
        assert _balance(u.id) == 0

    def test_spend_up_to_is_capped_and_idempotent(self):
        u = _user()
        have = _balance(u.id)
        assert credits.spend_up_to(u.id, "j", "process", have + 100) == have
        assert credits.spend_up_to(u.id, "j", "process", 5) == 0
        assert _balance(u.id) == 0

    def test_users_are_isolated(self):
        a, b = _user("a@example.com"), _user("b@example.com")
        credits.reserve(a.id, "j", "process", 7)
        assert _balance(b.id) == plans.get_plan("free").credits


class TestGrantsOrdering:
    def test_plan_credits_are_spent_before_topups(self):
        u = _user()
        with db.connection() as c:
            c.execute("UPDATE users SET plan = 'starter' WHERE id = ?", (u.id,))
        credits.grant(u.id, "plan", 100, expires_at=db.now() + 3600, source_ref="p1")
        credits.grant(u.id, "topup", 50, expires_at=None, source_ref="t1")
        credits.reserve(u.id, "j", "process", 120)
        b = credits.balance(u.id)
        assert b["plan_remaining"] == 0 and b["topup_remaining"] == 30

    def test_refund_returns_credits_to_the_grant_they_came_from(self):
        u = _user()
        with db.connection() as c:
            c.execute("UPDATE users SET plan = 'starter' WHERE id = ?", (u.id,))
        credits.grant(u.id, "plan", 100, expires_at=db.now() + 3600, source_ref="p1")
        credits.grant(u.id, "topup", 50, expires_at=None, source_ref="t1")
        lid = credits.reserve(u.id, "j", "process", 120)
        credits.release(lid)
        b = credits.balance(u.id)
        assert b["plan_remaining"] == 100 and b["topup_remaining"] == 50

    def test_expired_grants_do_not_count(self):
        u = _user()
        with db.connection() as c:
            c.execute("UPDATE users SET plan = 'starter' WHERE id = ?", (u.id,))
        credits.grant(u.id, "plan", 100, expires_at=db.now() - 1, source_ref="old")
        assert _balance(u.id) == 0

    def test_grant_is_idempotent_per_source_ref(self):
        u = _user()
        assert credits.grant(u.id, "topup", 10, source_ref="evt_1") is True
        assert credits.grant(u.id, "topup", 10, source_ref="evt_1") is False
        assert credits.grant(u.id, "topup", 0, source_ref="evt_2") is False


class TestBudgetAndConcurrency:
    def test_daily_budget_stops_api_backed_spend(self, monkeypatch):
        monkeypatch.setenv("DAILY_AI_BUDGET_CREDITS", "20")
        u = _user()
        credits.reserve(u.id, "a", "ai_short", 15, budgeted=True)
        with pytest.raises(credits.BudgetError):
            credits.reserve(u.id, "b", "ai_short", 10, budgeted=True)
        credits.reserve(u.id, "c", "process", 10)     # unbudgeted work is unaffected

    def test_concurrent_reserves_never_overspend(self):
        u = _user()
        have = _balance(u.id)
        results = []

        def go(i):
            try:
                credits.reserve(u.id, f"job{i}", "process", 10)
                results.append(True)
            except credits.QuotaError:
                results.append(False)

        threads = [threading.Thread(target=go, args=(i,)) for i in range(12)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        assert sum(results) == have // 10
        assert _balance(u.id) == have - 10 * sum(results)

    def test_stale_reservations_are_released(self):
        u = _user()
        have = _balance(u.id)
        lid = credits.reserve(u.id, "stuck", "process", 9)
        with db.connection() as c:
            c.execute("UPDATE credit_ledger SET updated_at = ? WHERE id = ?",
                      (db.now() - 7 * 3600, lid))
        assert credits.expire_stale_reservations() == 1
        assert _balance(u.id) == have
