"""studio/: accounts, project library, brand kits, usage. Each test gets its own DB."""
import io
import os
import time

import pytest

from studio import auth, brand_kits, db, projects, security, usage


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_DB_PATH", str(tmp_path / "studio.db"))
    monkeypatch.setenv("STUDIO_SECRET", "test-secret")
    monkeypatch.delenv("STUDIO_MONTHLY_MINUTES", raising=False)
    db._initialised_for = None
    auth.clear_all_throttles()
    db.init()
    yield


def _user(email="a@example.com", password="correct horse"):
    return auth.register(email, password, "Ann")


# --- security ----------------------------------------------------------------
class TestSecurity:
    def test_password_hash_roundtrip_and_salting(self):
        a = security.hash_password("hunter2hunter2")
        b = security.hash_password("hunter2hunter2")
        assert a != b                      # random salt
        assert security.verify_password("hunter2hunter2", a)
        assert not security.verify_password("wrong-password", a)
        assert not security.verify_password("x", "garbage")

    def test_token_roundtrip_and_tamper(self):
        token = security.create_token(7, 0)
        assert security.verify_token(token)["sub"] == "7"
        head, payload, sig = token.split(".")
        assert security.verify_token(f"{head}.{payload}.{sig[:-2]}xx") is None
        assert security.verify_token(f"{head}.{payload}x.{sig}") is None
        assert security.verify_token("not-a-token") is None

    def test_expired_token_rejected(self):
        assert security.verify_token(security.create_token(1, 0, ttl=-5)) is None

    def test_alg_none_is_rejected(self):
        import base64, json
        b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
        forged = f"{b({'alg': 'none'})}.{b({'sub': '1', 'tv': 0, 'exp': 9999999999})}."
        assert security.verify_token(forged) is None

    def test_resource_signature(self):
        exp = int(time.time()) + 60
        sig = security.sign_resource("logo", 3, exp)
        assert security.check_resource("logo", 3, exp, sig)
        assert not security.check_resource("logo", 4, exp, sig)
        assert not security.check_resource("logo", 3, exp - 120, security.sign_resource("logo", 3, exp - 120))


# --- accounts ---------------------------------------------------------------
class TestAuth:
    def test_register_and_login(self):
        user = _user()
        assert user.email == "a@example.com" and user.plan == "free"
        again = auth.login("A@Example.com", "correct horse")
        assert again.id == user.id

    def test_duplicate_email_is_rejected_case_insensitively(self):
        _user("dup@example.com")
        with pytest.raises(auth.AuthError) as e:
            _user("DUP@example.com")
        assert e.value.code == "email_taken"

    @pytest.mark.parametrize("email", ["", "nope", "a@b", "a b@c.com", "@x.com"])
    def test_bad_email(self, email):
        with pytest.raises(auth.AuthError) as e:
            auth.register(email, "correct horse")
        assert e.value.code == "invalid_email"

    def test_weak_password(self):
        with pytest.raises(auth.AuthError) as e:
            auth.register("w@example.com", "short")
        assert e.value.code == "weak_password"

    def test_wrong_password_and_unknown_user_look_identical(self):
        _user()
        with pytest.raises(auth.AuthError) as wrong:
            auth.login("a@example.com", "bad password!")
        with pytest.raises(auth.AuthError) as unknown:
            auth.login("ghost@example.com", "bad password!")
        assert (wrong.value.code, wrong.value.status) == (unknown.value.code, unknown.value.status) == ("bad_credentials", 401)

    def test_login_is_throttled(self):
        _user()
        for _ in range(8):
            with pytest.raises(auth.AuthError):
                auth.login("a@example.com", "bad password!", "1.2.3.4")
        with pytest.raises(auth.AuthError) as e:
            auth.login("a@example.com", "bad password!", "1.2.3.4")
        assert e.value.status == 429
        # a correct password from the same place is also held back until the window passes
        with pytest.raises(auth.AuthError) as held:
            auth.login("a@example.com", "correct horse", "1.2.3.4")
        assert held.value.status == 429

    def test_password_change_revokes_old_tokens(self):
        user = _user()
        old = auth.issue_token(user)
        assert auth.user_from_token(old).id == user.id
        updated = auth.change_password(user.id, "correct horse", "a brand new pass")
        assert auth.user_from_token(old) is None
        assert auth.user_from_token(auth.issue_token(updated)).id == user.id
        assert auth.login("a@example.com", "a brand new pass").id == user.id

    def test_change_password_needs_current(self):
        user = _user()
        with pytest.raises(auth.AuthError):
            auth.change_password(user.id, "nope nope nope", "a brand new pass")

    def test_delete_account_cascades(self):
        user = _user()
        projects.create("job-1", user.id, "T", "file")
        brand_kits.create(user.id, {"name": "K"})
        auth.delete_account(user.id, "correct horse")
        assert auth.get(user.id) is None
        assert projects.get_by_job("job-1") is None
        with db.connection() as c:
            assert c.execute("SELECT COUNT(*) FROM brand_kits").fetchone()[0] == 0

    def test_request_without_bearer_is_anonymous(self):
        class R:
            headers = {}
        assert auth.user_from_request(R()) is None


# --- projects --------------------------------------------------------------------
class TestProjects:
    def test_users_only_see_their_own(self):
        a, b = _user("a@example.com"), _user("b@example.com")
        projects.create("job-a", a.id, "Alpha", "file")
        projects.create("job-b", b.id, "Beta", "url", "https://x")
        assert [p["job_id"] for p in projects.list_for_user(a.id)["items"]] == ["job-a"]
        assert projects.get_for_user(a.id, "job-b") is None
        assert projects.rename(a.id, "job-b", "stolen") is None
        assert projects.delete(a.id, "job-b") is None
        assert projects.get_by_job("job-b")["title"] == "Beta"

    def test_search_filter_sort(self):
        u = _user()
        projects.create("j1", u.id, "Podcast about money", "file")
        projects.create("j2", u.id, "Cooking 101", "file")
        projects.create("j3", u.id, "100% real_deal", "file")
        projects.finish("j1", "completed", clip_count=5, top_score=91)
        projects.finish("j2", "completed", clip_count=2, top_score=40)
        assert [p["job_id"] for p in projects.list_for_user(u.id, q="money")["items"]] == ["j1"]
        # LIKE wildcards in the query are literal text
        assert [p["job_id"] for p in projects.list_for_user(u.id, q="100%")["items"]] == ["j3"]
        assert [p["job_id"] for p in projects.list_for_user(u.id, q="real_")["items"]] == ["j3"]
        assert projects.list_for_user(u.id, status="completed")["total"] == 2
        assert projects.list_for_user(u.id, status="active")["items"][0]["job_id"] == "j3"
        assert [p["job_id"] for p in projects.list_for_user(u.id, sort="score")["items"]][:2] == ["j1", "j2"]
        assert projects.list_for_user(u.id, limit=1)["items"].__len__() == 1

    def test_finish_keeps_a_title_the_user_chose(self):
        u = _user()
        projects.create("j1", u.id, "My own name", "file", source_ref="clip.mp4")
        projects.finish("j1", "completed", title="auto title")
        assert projects.get_by_job("j1")["title"] == "My own name"
        projects.create("j2", u.id, "clip.mp4", "file", source_ref="clip.mp4")
        projects.finish("j2", "completed", title="auto title")
        assert projects.get_by_job("j2")["title"] == "auto title"

    def test_rename_rejects_blank(self):
        u = _user()
        projects.create("j1", u.id, "Keep", "file")
        assert projects.rename(u.id, "j1", "   ") is None
        assert projects.get_by_job("j1")["title"] == "Keep"

    def test_status_transitions_stamp_finished_at(self):
        u = _user()
        projects.create("j1", u.id, "T", "file")
        projects.set_status("j1", "processing")
        assert projects.get_by_job("j1")["finished_at"] is None
        projects.set_status("j1", "cancelled")
        assert projects.get_by_job("j1")["finished_at"] is not None


# --- usage ------------------------------------------------------------------------
class TestUsage:
    def test_minutes_round_up_with_minimum_one(self):
        assert usage.minutes_for(0) == 1
        assert usage.minutes_for(59) == 1
        assert usage.minutes_for(61) == 2
        assert usage.minutes_for(3600) == 60

    def test_quota_enforced(self, monkeypatch):
        monkeypatch.setenv("STUDIO_MONTHLY_MINUTES", "10")
        u = _user()
        usage.check_can_start(u.id, 10)
        usage.charge(u.id, "j1", 8)
        usage.check_can_start(u.id, 2)
        with pytest.raises(usage.QuotaError) as e:
            usage.check_can_start(u.id, 3)
        assert e.value.remaining == 2 and e.value.limit == 10
        assert usage.summary(u.id) == {"limit": 10, "used": 8, "remaining": 2, "unlimited": False}

    def test_zero_means_unlimited(self, monkeypatch):
        monkeypatch.setenv("STUDIO_MONTHLY_MINUTES", "0")
        u = _user()
        usage.charge(u.id, "j1", 99999)
        usage.check_can_start(u.id, 99999)
        assert usage.summary(u.id)["unlimited"] is True

    def test_charge_is_idempotent_per_job(self):
        u = _user()
        assert usage.charge(u.id, "j1", 5) is True
        assert usage.charge(u.id, "j1", 5) is False
        assert usage.used_minutes(u.id) == 5

    def test_allowance_is_per_user(self, monkeypatch):
        monkeypatch.setenv("STUDIO_MONTHLY_MINUTES", "5")
        a, b = _user("a@example.com"), _user("b@example.com")
        usage.charge(a.id, "j1", 5)
        usage.check_can_start(b.id, 5)
        with pytest.raises(usage.QuotaError):
            usage.check_can_start(a.id, 1)

    def test_old_charges_do_not_count_this_month(self):
        u = _user()
        with db.connection() as c:
            c.execute("INSERT INTO usage_ledger (user_id, job_id, minutes, created_at) VALUES (?,?,?,?)",
                      (u.id, "old", 500, time.time() - 70 * 86400))
        assert usage.used_minutes(u.id) == 0


# --- brand kits -------------------------------------------------------------------
def _png(size=(32, 32), color=(255, 0, 0, 255)):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGBA", size, color).save(buf, format="PNG")
    return buf.getvalue()


class TestBrandKits:
    def test_first_kit_becomes_default_and_defaults_move(self):
        u = _user()
        k1 = brand_kits.create(u.id, {"name": "One"})
        k2 = brand_kits.create(u.id, {"name": "Two"})
        assert k1["is_default"] and not k2["is_default"]
        brand_kits.update(u.id, k2["id"], {"is_default": True})
        flags = {k["name"]: k["is_default"] for k in brand_kits.list_for_user(u.id)}
        assert flags == {"One": False, "Two": True}

    def test_deleting_default_promotes_another(self):
        u = _user()
        k1 = brand_kits.create(u.id, {"name": "One"})
        brand_kits.create(u.id, {"name": "Two"})
        assert brand_kits.delete(u.id, k1["id"])
        assert [k["is_default"] for k in brand_kits.list_for_user(u.id)] == [True]

    @pytest.mark.parametrize("bad", [
        {"logo_position": "middle"}, {"layout": "weird"}, {"primary_color": "red"},
        {"primary_color": "#12345"}, {"logo_opacity": 2}, {"logo_scale": 0.9}, {"name": ""},
        {"name": "x" * 61}, {"hook_style": "neon-pink"},
    ])
    def test_validation(self, bad):
        u = _user()
        with pytest.raises(brand_kits.KitError):
            brand_kits.create(u.id, bad)

    def test_kits_are_private_to_their_owner(self):
        a, b = _user("a@example.com"), _user("b@example.com")
        kit = brand_kits.create(a.id, {"name": "Mine"})
        assert brand_kits.get_for_user(b.id, kit["id"]) is None
        assert brand_kits.update(b.id, kit["id"], {"name": "Hacked"}) is None
        assert brand_kits.delete(b.id, kit["id"]) is False
        assert brand_kits.save_logo(b.id, kit["id"], _png()) is None
        assert brand_kits.resolve_for_job(b.id, kit["id"]) is None
        assert brand_kits.get_for_user(a.id, kit["id"])["name"] == "Mine"

    def test_logo_upload_replaces_and_deletes_files(self):
        u = _user()
        kit = brand_kits.create(u.id, {"name": "K"})
        first = brand_kits.save_logo(u.id, kit["id"], _png())
        assert first["has_logo"]
        path1 = brand_kits.logo_path_for_user(u.id, kit["id"])
        assert os.path.exists(path1)
        brand_kits.save_logo(u.id, kit["id"], _png(color=(0, 255, 0, 255)))
        path2 = brand_kits.logo_path_for_user(u.id, kit["id"])
        assert path2 != path1 and not os.path.exists(path1) and os.path.exists(path2)
        brand_kits.delete(u.id, kit["id"])
        assert not os.path.exists(path2)

    def test_logo_must_be_a_real_image(self):
        u = _user()
        kit = brand_kits.create(u.id, {"name": "K"})
        with pytest.raises(brand_kits.KitError) as e:
            brand_kits.save_logo(u.id, kit["id"], b"<html>not an image</html>")
        assert e.value.code == "invalid_logo"
        with pytest.raises(brand_kits.KitError) as big:
            brand_kits.save_logo(u.id, kit["id"], b"0" * (brand_kits.MAX_LOGO_BYTES + 1))
        assert big.value.status == 413

    def test_resolve_for_job_defaults_and_includes_logo_file(self):
        u = _user()
        assert brand_kits.resolve_for_job(u.id, None) is None
        kit = brand_kits.create(u.id, {"name": "K", "primary_color": "#abcdef"})
        brand_kits.save_logo(u.id, kit["id"], _png())
        resolved = brand_kits.resolve_for_job(u.id, None)
        assert resolved["primary_color"] == "#ABCDEF"
        assert resolved["logo_file"] and os.path.exists(resolved["logo_file"])

    def test_kit_limit(self, monkeypatch):
        monkeypatch.setattr(brand_kits, "MAX_KITS_PER_USER", 2)
        u = _user()
        brand_kits.create(u.id, {"name": "1"})
        brand_kits.create(u.id, {"name": "2"})
        with pytest.raises(brand_kits.KitError) as e:
            brand_kits.create(u.id, {"name": "3"})
        assert e.value.status == 409
