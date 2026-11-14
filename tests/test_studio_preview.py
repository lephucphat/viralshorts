import pytest

from studio import preview


@pytest.fixture(autouse=True)
def _clear():
    preview._cache.clear()


def _info(**kw):
    base = {"title": "  Hay   quá ", "uploader": "Kênh A", "thumbnail": "https://img.example/x.jpg",
            "duration": 754.6, "extractor_key": "Youtube"}
    base.update(kw)
    return base


def test_public_shape_is_clean():
    out = preview.fetch("https://example.com/v", extract=lambda u: _info())
    assert out == {"title": "Hay quá", "channel": "Kênh A", "thumbnail": "https://img.example/x.jpg",
                   "duration": 754, "live": False, "site": "Youtube"}


def test_unsafe_thumbnail_scheme_dropped_and_falls_back_to_list():
    out = preview.fetch("https://example.com/a", extract=lambda u: _info(thumbnail="javascript:alert(1)"))
    assert out["thumbnail"] == ""
    out = preview.fetch("https://example.com/b", extract=lambda u: _info(
        thumbnail="", thumbnails=[{"url": "https://i/1.jpg"}, {"url": "https://i/2.jpg"}]))
    assert out["thumbnail"] == "https://i/2.jpg"


def test_blocked_url_never_reaches_the_extractor():
    called = []

    def refuse(url):
        raise ValueError("private")

    with pytest.raises(preview.PreviewError) as e:
        preview.fetch("http://10.0.0.1/x", check_url=refuse, extract=lambda u: called.append(u) or _info())
    assert e.value.code == "bad_url" and called == []


def test_extractor_failure_and_empty_result():
    def boom(url):
        raise RuntimeError("yt-dlp exploded with secrets")

    with pytest.raises(preview.PreviewError) as e:
        preview.fetch("https://example.com/c", extract=boom)
    assert e.value.code == "unavailable" and "secrets" not in str(e.value)
    with pytest.raises(preview.PreviewError):
        preview.fetch("https://example.com/d", extract=lambda u: {})
    with pytest.raises(preview.PreviewError):
        preview.fetch("   ")


def test_cached_for_repeat_pastes():
    n = []
    preview.fetch("https://example.com/e", extract=lambda u: n.append(1) or _info())
    preview.fetch("https://example.com/e", extract=lambda u: n.append(1) or _info())
    assert len(n) == 1
