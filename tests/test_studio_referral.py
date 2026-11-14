"""Friend referrals (studio/referral.py): code per person, reward on the friend's FIRST payment."""
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from studio import api, auth, credits, db, plans, promo, referral
from studio.payments import service, stripe_provider


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_DB_PATH", str(tmp_path / "studio.db"))
    monkeypatch.setenv("STUDIO_SECRET", "test-secret")
    monkeypatch.setenv("STUDIO_PAID", "1")
    monkeypatch.setenv("REFERRAL_REWARD_CREDITS", "25")
    monkeypatch.delenv("REFERRAL_MAX_REWARDS", raising=False)
    db._initialised_for = None
    auth.clear_all_throttles()
    ctx = api.Context(job_status=lambda j: None, cancel_job=lambda j: False, remove_job_files=lambda j: None)
    app = FastAPI()
    app.include_router(api.build_router(ctx))
    return TestClient(app)


def _user(email):
    return auth.register(email, "correct horse", "T")


def _hdr(user):
    return {"Authorization": f"Bearer {auth.issue_token(user)}"}


def _pay(user, n=1):
    """A paid payment through the real recording path (what both webhooks call)."""
    with db.write_connection() as c:
        service.record_payment(c, user.id, "stripe", f"in_{user.id}_{n}", "subscription", "starter",
                               1200, "usd", plans.PLANS["starter"].credits, "paid", db.now())


def _topups(uid):
    with db.connection() as c:
        return [r["amount"] for r in c.execute(
            "SELECT amount FROM credit_grants WHERE user_id = ? AND kind = 'topup'", (uid,))]


def test_each_person_gets_one_stable_code(client):
    a = _user("a@example.com")
    s = client.get("/api/referral", headers=_hdr(a)).json()
    assert s["enabled"] and s["reward_credits"] == 25 and s["code"].startswith("VS-")
    assert client.get("/api/referral", headers=_hdr(a)).json()["code"] == s["code"]
    assert client.get("/api/referral", headers=_hdr(_user("b@example.com"))).json()["code"] != s["code"]


def test_off_outside_the_paid_edition_or_with_zero_reward(client, monkeypatch):
    a = _user("a@example.com")
    monkeypatch.setenv("REFERRAL_REWARD_CREDITS", "0")
    assert client.get("/api/referral", headers=_hdr(a)).json() == {
        "enabled": False, "reward_credits": 0, "code": None, "invited": 0, "rewarded": 0,
        "credits_earned": 0, "attached": None}
    assert client.post("/api/referral/attach", json={"code": "VS-AAAAAAA"}, headers=_hdr(a)).status_code == 404
    monkeypatch.setenv("REFERRAL_REWARD_CREDITS", "25")
    monkeypatch.setenv("STUDIO_PAID", "0")
    assert client.get("/api/referral", headers=_hdr(a)).json()["enabled"] is False


def test_referral_code_cannot_be_redeemed_as_a_plain_promo(client):
    a, b = _user("a@example.com"), _user("b@example.com")
    code = referral.code_for(a.id)
    with pytest.raises(promo.PromoError) as e:
        promo.redeem(b.id, code)
    assert e.value.code == "invalid_code"
    assert credits.balance(b.id)["remaining"] == credits.balance(_user("c@example.com").id)["remaining"]


def test_both_sides_are_paid_once_on_the_first_payment_only(client):
    a, b = _user("a@example.com"), _user("b@example.com")
    code = referral.code_for(a.id)
    r = client.post("/api/referral/attach", json={"code": code.lower()}, headers=_hdr(b))
    assert r.status_code == 200 and r.json()["attached"] == {"status": "pending", "reward_credits": 0}
    assert _topups(a.id) == [] and _topups(b.id) == []              # nothing before the friend pays

    _pay(b, 1)
    assert _topups(a.id) == [25] and _topups(b.id) == [25]
    _pay(b, 1)                                                     # the same payment replayed
    _pay(b, 2)                                                     # a renewal
    assert _topups(a.id) == [25] and _topups(b.id) == [25]

    sa = client.get("/api/referral", headers=_hdr(a)).json()
    assert (sa["invited"], sa["rewarded"], sa["credits_earned"]) == (1, 1, 25)
    sb = client.get("/api/referral", headers=_hdr(b)).json()
    assert sb["attached"] == {"status": "rewarded", "reward_credits": 25}
    with db.connection() as c:
        assert c.execute("SELECT used FROM promo_codes WHERE code = ?", (code,)).fetchone()["used"] == 1


def test_a_pending_payment_pays_nothing_until_it_is_paid(client):
    a, b = _user("a@example.com"), _user("b@example.com")
    referral.attach(b.id, referral.code_for(a.id))
    with db.write_connection() as c:
        service.record_payment(c, b.id, "payos", "123456789012", "subscription", "starter", 99000, "vnd", 0, "pending")
    assert _topups(a.id) == [] and _topups(b.id) == []
    with db.write_connection() as c:
        service.record_payment(c, b.id, "payos", "123456789012", "subscription", "starter", 99000, "vnd",
                               300, "paid", db.now())
    assert _topups(a.id) == [25] and _topups(b.id) == [25]


@pytest.mark.parametrize("make,code", [
    (lambda a, b: referral.code_for(b.id), "own_code"),
    (lambda a, b: "VS-NOPE123", "invalid_code"),
    (lambda a, b: "SUMMER2026", "invalid_code"),           # an ordinary promo code is not a referral code
    (lambda a, b: "x", "invalid_code"),
])
def test_attach_refusals(client, make, code):
    a, b = _user("a@example.com"), _user("b@example.com")
    promo.create("SUMMER2026", 10)
    with pytest.raises(referral.ReferralError) as e:
        referral.attach(b.id, make(a, b))
    assert e.value.code == code


def test_same_inbox_under_another_alias_is_not_a_friend(client):
    # Sign-up already refuses aliases of one inbox; an address changed later could still end up
    # canonically equal, so the referral check compares canonical addresses on its own.
    a = _user("someone@gmail.com")
    twin = _user("other@example.com")
    with db.connection() as c:
        c.execute("UPDATE users SET email_canonical = 'someone@gmail.com' WHERE id = ?", (twin.id,))
    with pytest.raises(referral.ReferralError) as e:
        referral.attach(twin.id, referral.code_for(a.id))
    assert e.value.code == "own_code"


def test_one_referrer_per_account_and_not_after_paying(client):
    a, c, b = _user("a@example.com"), _user("c@example.com"), _user("b@example.com")
    referral.attach(b.id, referral.code_for(a.id))
    with pytest.raises(referral.ReferralError) as e:
        referral.attach(b.id, referral.code_for(c.id))
    assert e.value.code == "already_referred"

    d = _user("d@example.com")
    _pay(d)
    with pytest.raises(referral.ReferralError) as e2:
        referral.attach(d.id, referral.code_for(a.id))
    assert e2.value.code == "already_customer"
    assert client.get("/api/referral", headers=_hdr(d)).json()["can_attach"] is False


def test_switched_off_code_stops_working(client):
    a, b = _user("a@example.com"), _user("b@example.com")
    code = referral.code_for(a.id)
    promo.set_active(code, False)
    with pytest.raises(referral.ReferralError):
        referral.attach(b.id, code)


def test_referrer_ceiling_voids_extra_links_without_paying(client, monkeypatch):
    monkeypatch.setenv("REFERRAL_MAX_REWARDS", "1")
    a = _user("a@example.com")
    code = referral.code_for(a.id)
    for i in range(2):
        f = _user(f"f{i}@example.com")
        referral.attach(f.id, code)
        _pay(f)
    assert _topups(a.id) == [25]                                    # only the first friend paid out
    with db.connection() as c:
        st = [r["status"] for r in c.execute("SELECT status FROM referrals ORDER BY id")]
    assert st == ["rewarded", "void"]


def test_attach_is_throttled(client):
    a, b = _user("a@example.com"), _user("b@example.com")
    for _ in range(10):
        with pytest.raises(referral.ReferralError):
            referral.attach(b.id, "VS-NOPE123")
    with pytest.raises(auth.AuthError):
        referral.attach(b.id, "VS-NOPE123")


def test_deleting_the_referrer_removes_their_code_and_links(client):
    a, b = _user("a@example.com"), _user("b@example.com")
    code = referral.code_for(a.id)
    referral.attach(b.id, code)
    auth.erase_account(a.id)
    assert promo.get(code) is None
    with db.connection() as c:
        assert c.execute("SELECT COUNT(*) AS n FROM referrals").fetchone()["n"] == 0


def test_stripe_invoice_path_rewards_end_to_end(client):
    a, b = _user("a@example.com"), _user("b@example.com")
    referral.attach(b.id, referral.code_for(a.id))
    now = int(db.now())
    stripe_provider.handle_event({"id": "evt_c", "type": "checkout.session.completed", "data": {"object": {
        "id": "cs_1", "mode": "subscription", "customer": "cus_1", "subscription": "sub_1",
        "client_reference_id": str(b.id), "payment_status": "paid", "amount_total": 1200, "currency": "usd",
        "metadata": {"user_id": str(b.id), "kind": "subscription", "item": "starter"}}}})
    stripe_provider.handle_event({"id": "evt_i", "type": "invoice.paid", "data": {"object": {
        "id": "in_1", "subscription": "sub_1", "customer": "cus_1", "amount_paid": 1200, "currency": "usd",
        "lines": {"data": [{"period": {"start": now - 5, "end": now + 30 * 86400}}]}}}})
    assert _topups(a.id) == [25] and _topups(b.id) == [25]
    assert service.active_subscription(b.id)["plan"] == "starter"
