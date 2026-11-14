"""studio/payments: webhook verification, idempotency and what a payment grants.

No network: events are built by hand and signed with the same HMAC scheme the
providers use. Each test gets its own database.
"""
import hashlib
import hmac
import json

import pytest

from studio import auth, credits, db, plans
from studio.payments import payos_provider, service, stripe_provider

STRIPE_SECRET = "whsec_test"
PAYOS_KEY = "checksum-test-key"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_DB_PATH", str(tmp_path / "studio.db"))
    monkeypatch.setenv("STUDIO_SECRET", "test-secret")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", STRIPE_SECRET)
    monkeypatch.setenv("PAYOS_CHECKSUM_KEY", PAYOS_KEY)
    db._initialised_for = None
    auth.clear_all_throttles()
    db.init()
    yield


def _user(email="a@example.com"):
    return auth.register(email, "correct horse", "Ann")


def _balance(uid):
    return credits.balance(uid)


def _plan(uid):
    with db.connection() as c:
        return c.execute("SELECT plan FROM users WHERE id = ?", (uid,)).fetchone()["plan"]


# ---- Stripe: signatures ----------------------------------------------------------------------
def _stripe_header(payload: bytes, secret=STRIPE_SECRET, t=1_700_000_000):
    sig = hmac.new(secret.encode(), f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={t},v1={sig}"


class TestStripeSignature:
    payload = json.dumps({"id": "evt_1", "type": "x"}).encode()

    def test_valid_signature_returns_the_event(self):
        ev = stripe_provider.verify_webhook(self.payload, _stripe_header(self.payload), now=1_700_000_100)
        assert ev["id"] == "evt_1"

    def test_wrong_secret_tampered_body_and_garbage_are_refused(self):
        for header, body in [
            (_stripe_header(self.payload, secret="other"), self.payload),
            (_stripe_header(self.payload), self.payload + b" "),
            ("", self.payload), ("t=abc,v1=00", self.payload), ("nonsense", self.payload),
        ]:
            with pytest.raises(stripe_provider.SignatureError):
                stripe_provider.verify_webhook(body, header, now=1_700_000_100)

    def test_old_timestamp_is_refused_so_a_capture_cannot_be_replayed(self):
        with pytest.raises(stripe_provider.SignatureError):
            stripe_provider.verify_webhook(self.payload, _stripe_header(self.payload), now=1_700_000_000 + 3600)

    def test_any_of_several_v1_signatures_may_match(self):
        good = _stripe_header(self.payload).split("v1=")[1]
        header = f"t=1700000000,v1={'0' * 64},v1={good}"
        assert stripe_provider.verify_webhook(self.payload, header, now=1_700_000_100)["id"] == "evt_1"


# ---- Stripe: events --------------------------------------------------------------------------
def _checkout_event(uid, **kw):
    obj = {"id": "cs_1", "mode": "subscription", "customer": "cus_1", "subscription": "sub_1",
           "client_reference_id": str(uid),
           "metadata": {"user_id": str(uid), "kind": "subscription", "item": "starter"},
           "payment_status": "paid", "amount_total": 1200, "currency": "usd"}
    obj.update(kw)
    return {"id": kw.pop("event_id", "evt_checkout"), "type": "checkout.session.completed",
            "data": {"object": obj}}


def _invoice_event(inv_id="in_1", sub="sub_1", start=1_700_000_000, end=None, customer="cus_1",
                   event_id=None, **extra):
    end = end or start + 30 * 86400
    obj = {"id": inv_id, "subscription": sub, "customer": customer, "amount_paid": 1200,
           "currency": "usd", "lines": {"data": [{"period": {"start": start, "end": end}}]}}
    obj.update(extra)
    return {"id": event_id or f"evt_{inv_id}", "type": "invoice.paid", "data": {"object": obj}}


class TestStripeTopup:
    def test_paid_topup_grants_credits_once(self):
        u = _user()
        ev = _checkout_event(u.id, mode="payment", subscription=None,
                             metadata={"user_id": str(u.id), "kind": "topup", "item": "topup_100"})
        free = _balance(u.id)["remaining"]
        assert stripe_provider.handle_event(ev) == "applied"
        assert _balance(u.id)["topup_remaining"] == 100
        assert _balance(u.id)["remaining"] == free + 100
        assert stripe_provider.handle_event(ev) == "duplicate"        # a webhook retry
        assert _balance(u.id)["topup_remaining"] == 100
        pay = service.payments_for_user(u.id)
        assert len(pay) == 1 and pay[0]["status"] == "paid" and pay[0]["credits"] == 100

    def test_unpaid_session_grants_nothing(self):
        u = _user()
        ev = _checkout_event(u.id, mode="payment", subscription=None, payment_status="unpaid",
                             metadata={"user_id": str(u.id), "kind": "topup", "item": "topup_100"})
        assert stripe_provider.handle_event(ev) == "ignored"
        assert _balance(u.id)["topup_remaining"] == 0

    def test_unknown_pack_grants_nothing(self):
        u = _user()
        ev = _checkout_event(u.id, mode="payment", subscription=None,
                             metadata={"user_id": str(u.id), "kind": "topup", "item": "free_money"})
        assert stripe_provider.handle_event(ev) == "ignored"


class TestStripeSubscription:
    def test_checkout_alone_does_not_start_the_plan(self):
        u = _user()
        stripe_provider.handle_event(_checkout_event(u.id))
        assert _plan(u.id) == "free"                       # paid status comes from the invoice
        assert service.user_by_customer(db.connection().__enter__(), "stripe", "cus_1") == u.id

    def test_paid_invoice_activates_plan_and_grants_period_credits(self):
        u = _user()
        stripe_provider.handle_event(_checkout_event(u.id))
        inv = _invoice_event(start=int(db.now()) - 10, end=int(db.now()) + 30 * 86400)
        assert stripe_provider.handle_event(inv) == "applied"
        assert _plan(u.id) == "starter"
        b = _balance(u.id)
        assert b["plan_remaining"] == plans.PLANS["starter"].credits   # the free grant is gone: not free any more
        assert stripe_provider.handle_event(inv) == "duplicate"
        assert _balance(u.id)["plan_remaining"] == plans.PLANS["starter"].credits

    def test_renewal_grants_a_new_period_and_old_credits_expire(self):
        u = _user()
        stripe_provider.handle_event(_checkout_event(u.id))
        now = int(db.now())
        stripe_provider.handle_event(_invoice_event("in_1", start=now - 40 * 86400, end=now - 10 * 86400))
        # that period (and its renewal grace) is over: back on free, only this month's free credits
        assert _balance(u.id)["plan_remaining"] == plans.PLANS["free"].credits
        stripe_provider.handle_event(_invoice_event("in_2", start=now - 10, end=now + 30 * 86400))
        # a later renewal grants a fresh period (the free grant from the lapse is still live this month)
        assert _balance(u.id)["plan_remaining"] == plans.PLANS["starter"].credits + plans.PLANS["free"].credits

    def test_invoice_before_checkout_is_retried_not_lost(self):
        u = _user()
        # no metadata, unknown subscription and customer: we cannot tell whose it is yet
        with pytest.raises(service.UnknownUser):
            stripe_provider.handle_event(_invoice_event())
        with db.connection() as c:                                       # nothing was recorded
            assert c.execute("SELECT COUNT(*) AS n FROM payment_events").fetchone()["n"] == 0
        stripe_provider.handle_event(_checkout_event(u.id))
        now = int(db.now())
        assert stripe_provider.handle_event(
            _invoice_event(start=now - 5, end=now + 30 * 86400)) == "applied"   # the retry works
        assert _plan(u.id) == "starter"

    def test_invoice_can_name_the_user_in_its_own_metadata(self):
        u = _user()
        now = int(db.now())
        ev = _invoice_event(start=now - 5, end=now + 30 * 86400, customer="cus_new",
                            subscription_details={"metadata": {"user_id": str(u.id), "item": "pro"}})
        assert stripe_provider.handle_event(ev) == "applied"
        assert _plan(u.id) == "pro"

    def test_failed_payment_marks_past_due_but_keeps_the_plan_for_now(self):
        u = _user()
        stripe_provider.handle_event(_checkout_event(u.id))
        now = int(db.now())
        stripe_provider.handle_event(_invoice_event(start=now - 5, end=now + 30 * 86400))
        stripe_provider.handle_event({"id": "evt_fail", "type": "invoice.payment_failed",
                                      "data": {"object": {"id": "in_2", "subscription": "sub_1"}}})
        assert service.active_subscription(u.id)["status"] == "past_due"
        assert _plan(u.id) == "starter"

    def test_cancellation_returns_to_free_and_free_credits_resume(self):
        u = _user()
        stripe_provider.handle_event(_checkout_event(u.id))
        now = int(db.now())
        stripe_provider.handle_event(_invoice_event(start=now - 5, end=now + 30 * 86400))
        stripe_provider.handle_event({"id": "evt_del", "type": "customer.subscription.deleted",
                                      "data": {"object": {"id": "sub_1", "customer": "cus_1", "status": "canceled"}}})
        assert _plan(u.id) == "free"
        assert service.active_subscription(u.id) is None
        # the paid period's credits stay usable until they expire; this month's free grant arrives too
        assert _balance(u.id)["remaining"] >= plans.PLANS["starter"].credits

    def test_an_old_incomplete_update_cannot_undo_an_activated_subscription(self):
        u = _user()
        stripe_provider.handle_event(_checkout_event(u.id))
        now = int(db.now())
        stripe_provider.handle_event(_invoice_event(start=now - 5, end=now + 30 * 86400))
        stripe_provider.handle_event({"id": "evt_up", "type": "customer.subscription.updated",
                                      "data": {"object": {"id": "sub_1", "customer": "cus_1",
                                                          "status": "incomplete"}}})
        assert service.active_subscription(u.id)["status"] == "active"

    def test_unknown_event_types_are_ignored(self):
        assert stripe_provider.handle_event({"id": "evt_x", "type": "payout.paid", "data": {"object": {}}}) == "ignored"


# ---- PayOS -----------------------------------------------------------------------------------
def _payos_pending(uid, kind="subscription", item="starter", code="123456789012", amount=None):
    amount = amount or (plans.PLANS[item].price_vnd if kind == "subscription" else plans.PACKS[item].price_vnd)
    granted = plans.PLANS[item].credits if kind == "subscription" else plans.PACKS[item].credits
    with db.write_connection() as c:
        service.record_payment(c, uid, "payos", code, kind, item, amount, "vnd", granted, "pending")
    return code, amount


def _payos_webhook(code, amount, success=True, key=PAYOS_KEY):
    data = {"orderCode": int(code), "amount": amount, "description": f"VS{code}", "currency": "VND",
            "paymentLinkId": "plid", "code": "00" if success else "01", "desc": "ok",
            "counterAccountName": None}
    return {"code": "00" if success else "01", "desc": "success", "success": success, "data": data,
            "signature": payos_provider.data_signature(data, key)}


class TestPayOS:
    def test_signature_roundtrip_and_tamper(self):
        body = _payos_webhook("1", 100)
        assert payos_provider.verify_webhook(body)["amount"] == 100
        body["data"]["amount"] = 1
        with pytest.raises(payos_provider.SignatureError):
            payos_provider.verify_webhook(body)
        with pytest.raises(payos_provider.SignatureError):
            payos_provider.verify_webhook(_payos_webhook("1", 100, key="wrong-key"))
        with pytest.raises(payos_provider.SignatureError):
            payos_provider.verify_webhook({"data": {}, "signature": ""})

    def test_signature_covers_fields_in_sorted_order_with_empty_for_null(self):
        data = {"b": 2, "a": None, "c": "x"}
        expected = hmac.new(PAYOS_KEY.encode(), b"a=&b=2&c=x", hashlib.sha256).hexdigest()
        assert payos_provider.data_signature(data) == expected

    def test_paid_plan_order_activates_one_period(self):
        u = _user()
        code, amount = _payos_pending(u.id)
        assert payos_provider.handle_webhook(_payos_webhook(code, amount)) == "applied"
        assert _plan(u.id) == "starter"
        sub = service.active_subscription(u.id)
        assert sub["provider"] == "payos"
        assert sub["current_period_end"] - sub["current_period_start"] == payos_provider.PERIOD_SECONDS
        assert _balance(u.id)["plan_remaining"] == plans.PLANS["starter"].credits
        assert payos_provider.handle_webhook(_payos_webhook(code, amount)) == "duplicate"
        assert _balance(u.id)["plan_remaining"] == plans.PLANS["starter"].credits

    def test_topup_order(self):
        u = _user()
        code, amount = _payos_pending(u.id, "topup", "topup_500", "111111111111")
        assert payos_provider.handle_webhook(_payos_webhook(code, amount)) == "applied"
        assert _balance(u.id)["topup_remaining"] == 500

    def test_wrong_amount_unknown_order_and_unpaid_grant_nothing(self):
        u = _user()
        code, amount = _payos_pending(u.id)
        assert payos_provider.handle_webhook(_payos_webhook(code, amount - 1000)) == "ignored"
        assert payos_provider.handle_webhook(_payos_webhook("999999999999", amount)) == "ignored"
        assert payos_provider.handle_webhook(_payos_webhook(code, amount, success=False)) == "ignored"
        assert _plan(u.id) == "free"
        # and the real payment still works afterwards: nothing above used up the order
        assert payos_provider.handle_webhook(_payos_webhook(code, amount)) == "applied"

    def test_forged_webhook_is_refused(self):
        u = _user()
        code, amount = _payos_pending(u.id)
        with pytest.raises(payos_provider.SignatureError):
            payos_provider.handle_webhook(_payos_webhook(code, amount, key="attacker"))
        assert _plan(u.id) == "free"

    def test_paying_again_early_queues_the_next_period(self):
        u = _user()
        a, amount = _payos_pending(u.id, code="100000000001")
        b, _ = _payos_pending(u.id, code="100000000002")
        payos_provider.handle_webhook(_payos_webhook(a, amount))
        first_end = service.active_subscription(u.id)["current_period_end"]
        payos_provider.handle_webhook(_payos_webhook(b, amount))
        with db.connection() as c:
            ends = sorted(r["current_period_end"] for r in c.execute(
                "SELECT current_period_end FROM subscriptions WHERE user_id = ?", (u.id,)))
        assert ends[1] == pytest.approx(first_end + payos_provider.PERIOD_SECONDS, abs=2)

    def test_a_lapsed_prepaid_period_returns_the_account_to_free(self):
        u = _user()
        code, amount = _payos_pending(u.id)
        payos_provider.handle_webhook(_payos_webhook(code, amount))
        with db.connection() as c:
            c.execute("UPDATE subscriptions SET current_period_end = ? WHERE user_id = ?",
                      (db.now() - 5, u.id))
        assert service.expire_due_subscriptions() == 1
        assert _plan(u.id) == "free"
        assert service.expire_due_subscriptions() == 0


class TestPayOSAgainstTheDocs:
    """Facts taken from PayOS's published documentation, independent of our own helpers."""
    DOC_KEY = "1a54716c8f0efb2744fb28b6e38b25da7f67a925d98bc1c18bd8faaecadd7675"
    DOC_BODY = {
        "code": "00", "desc": "success", "success": True,
        "data": {"orderCode": 123, "amount": 3000, "description": "VQRIO123", "accountNumber": "12345678",
                 "reference": "TF230204212323", "transactionDateTime": "2023-02-04 18:25:00", "currency": "VND",
                 "paymentLinkId": "124c33293c43417ab7879e14c8d9eb18", "code": "00", "desc": "Thành công",
                 "counterAccountBankId": "", "counterAccountBankName": "", "counterAccountName": "",
                 "counterAccountNumber": "", "virtualAccountName": "", "virtualAccountNumber": ""},
        "signature": "412e915d2871504ed31be63c8f62a149a4410d34c4c42affc9006ef9917eaa03",
    }

    def test_the_documented_sample_webhook_verifies(self):
        assert payos_provider.verify_webhook(self.DOC_BODY, self.DOC_KEY)["orderCode"] == 123
        tampered = {**self.DOC_BODY, "data": {**self.DOC_BODY["data"], "amount": 1}}
        with pytest.raises(payos_provider.SignatureError):
            payos_provider.verify_webhook(tampered, self.DOC_KEY)

    def test_registration_ping_is_acknowledged_and_grants_nothing(self):
        # PayOS posts this (orderCode 123) when the webhook URL is registered.
        import os
        os.environ["PAYOS_CHECKSUM_KEY"] = self.DOC_KEY
        try:
            assert payos_provider.handle_webhook(self.DOC_BODY) == "ignored"
        finally:
            os.environ["PAYOS_CHECKSUM_KEY"] = PAYOS_KEY

    def test_order_code_and_description_fit_payos_limits(self):
        import time
        codes = []
        for _ in range(40):
            codes.append(payos_provider.new_order_code())
            time.sleep(0.002)                         # orders are never created within one millisecond
        assert len(set(codes)) == len(codes)
        assert all(0 < c < 2 ** 53 for c in codes)

    def test_request_signature_uses_the_documented_field_order(self):
        sig = payos_provider.request_signature(3000, "https://c", "VS000123", 123, "https://r", self.DOC_KEY)
        want = hmac.new(self.DOC_KEY.encode(),
                        b"amount=3000&cancelUrl=https://c&description=VS000123&orderCode=123&returnUrl=https://r",
                        hashlib.sha256).hexdigest()
        assert sig == want


class TestPayOSSync:
    @pytest.fixture(autouse=True)
    def _keys(self, monkeypatch):
        monkeypatch.setenv("PAYOS_CLIENT_ID", "cid")
        monkeypatch.setenv("PAYOS_API_KEY", "akey")

    def _fake(self, monkeypatch, status="PAID", paid=None, amount=None):
        def fake(code):
            return {"orderCode": int(code), "status": status, "amount": amount,
                    "amountPaid": amount if paid is None else paid}
        monkeypatch.setattr(payos_provider, "fetch_status", fake)

    def test_a_paid_order_is_applied_once_and_agrees_with_the_webhook(self, monkeypatch):
        u = _user()
        code, amount = _payos_pending(u.id)
        self._fake(monkeypatch, amount=amount)
        assert payos_provider.sync_order(u.id, code) == "applied"
        assert _plan(u.id) == "starter"
        assert payos_provider.sync_order(u.id, code) == "duplicate"
        assert payos_provider.handle_webhook(_payos_webhook(code, amount)) == "duplicate"   # no double grant

    def test_pending_underpaid_or_unknown_status_grants_nothing(self, monkeypatch):
        u = _user()
        code, amount = _payos_pending(u.id)
        self._fake(monkeypatch, status="PENDING", amount=amount)
        assert payos_provider.sync_order(u.id, code) == "pending"
        self._fake(monkeypatch, status="SOMETHING_NEW", amount=amount)
        assert payos_provider.sync_order(u.id, code) == "pending"
        self._fake(monkeypatch, status="PAID", paid=amount - 1000, amount=amount)
        assert payos_provider.sync_order(u.id, code) == "ignored"
        assert _plan(u.id) == "free"

    def test_nobody_can_confirm_someone_elses_order(self, monkeypatch):
        owner = _user()
        code, amount = _payos_pending(owner.id)
        self._fake(monkeypatch, amount=amount)
        other = auth.register("other@example.com", "correct horse", "Bob")
        assert payos_provider.sync_order(other.id, code) == "ignored"
        assert _plan(owner.id) == "free"
        assert payos_provider.sync_order(owner.id, "not-a-number") == "ignored"


class TestExpiry:
    def test_a_stripe_subscription_waits_out_the_renewal_grace(self):
        u = _user()
        stripe_provider.handle_event(_checkout_event(u.id))
        now = int(db.now())
        stripe_provider.handle_event(_invoice_event(start=now - 31 * 86400, end=now - 3600))
        assert service.expire_due_subscriptions() == 0              # one hour late: still waiting
        assert _plan(u.id) == "starter"
        with db.connection() as c:
            c.execute("UPDATE subscriptions SET current_period_end = ?", (now - 4 * 86400,))
        assert service.expire_due_subscriptions() == 1
        assert _plan(u.id) == "free"
