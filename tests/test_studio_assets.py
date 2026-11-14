"""studio/assets.py: what the tools made is kept per user, validated, capped and erased with the account."""
import pytest

from studio import assets, auth, db


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_DB_PATH", str(tmp_path / "studio.db"))
    monkeypatch.setenv("STUDIO_SECRET", "test-secret")
    db._initialised_for = None
    auth.clear_all_throttles()
    db.init()
    yield


def _user(email="a@example.com"):
    return auth.register(email, "correct horse", "Ann")


def _item(n, session="s1"):
    return {"url": f"/thumbnails/{session}/thumb_abc_{n}.jpg", "title": "My video", "text": f"T{n}"}


def test_add_list_and_isolation():
    a, b = _user("a@example.com"), _user("b@example.com")
    assets.add_many(a.id, "thumbnail", [_item(1), _item(2)])
    assert [x["text"] for x in assets.list_for_user(a.id, "thumbnail")] == ["T2", "T1"]
    assert assets.list_for_user(b.id) == []


def test_same_url_is_stored_once():
    a = _user()
    assets.add_many(a.id, "thumbnail", [_item(1)])
    assets.add_many(a.id, "thumbnail", [_item(1)])
    assert len(assets.list_for_user(a.id)) == 1


@pytest.mark.parametrize("url", ["/thumbnails/../../.env", "http://evil/x.jpg", "/videos/a/b.mp4",
                                 "/thumbnails/s1/..%2f.env", "/thumbnails/s1/a/b.jpg", ""])
def test_bad_urls_are_ignored(url):
    a = _user()
    assets.add_many(a.id, "thumbnail", [{"url": url, "title": "x"}])
    assert assets.list_for_user(a.id) == []


def test_unknown_kind_is_ignored():
    a = _user()
    assert assets.add_many(a.id, "nonsense", [_item(1)]) == []
    assert assets.list_for_user(a.id) == []


def test_delete_only_your_own():
    a, b = _user("a@example.com"), _user("b@example.com")
    assets.add_many(a.id, "thumbnail", [_item(1)])
    row = assets.list_for_user(a.id)[0]
    assert assets.delete(b.id, row["id"]) is None
    assert assets.delete(a.id, row["id"]) == row["url"]
    assert assets.list_for_user(a.id) == []


def test_cap_drops_oldest_and_returns_their_urls(monkeypatch):
    monkeypatch.setattr(assets, "KEEP_PER_USER", 3)
    a = _user()
    assets.add_many(a.id, "thumbnail", [_item(i) for i in range(1, 4)])
    dropped = assets.add_many(a.id, "thumbnail", [_item(4), _item(5)])
    assert sorted(dropped) == sorted([_item(1)["url"], _item(2)["url"]])
    assert len(assets.list_for_user(a.id)) == 3


def test_erasing_the_account_runs_hooks_and_cascades(monkeypatch):
    a = _user()
    assets.add_many(a.id, "thumbnail", [_item(1)])
    seen = []
    monkeypatch.setattr(auth, "_ERASE_HOOKS", [lambda uid: seen.append((uid, assets.urls_for_user(uid)))])
    auth.erase_account(a.id)
    assert seen == [(a.id, [_item(1)["url"]])]          # the hook still saw the urls
    with db.connection() as c:
        assert c.execute("SELECT COUNT(*) AS n FROM tool_assets").fetchone()["n"] == 0


def test_a_failing_erase_hook_does_not_block_deletion(monkeypatch):
    a = _user()

    def boom(_uid):
        raise RuntimeError("disk gone")
    monkeypatch.setattr(auth, "_ERASE_HOOKS", [boom])
    auth.erase_account(a.id)
    with db.connection() as c:
        assert c.execute("SELECT COUNT(*) AS n FROM users WHERE id = ?", (a.id,)).fetchone()["n"] == 0
