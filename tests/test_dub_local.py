"""dub_local: the low-cost dubbing pipeline (pure logic; no network, no ffmpeg)."""
import pytest

import dub_local


def test_tts_order_prefers_gateway_when_configured(monkeypatch):
    monkeypatch.delenv("DUB_TTS", raising=False)
    monkeypatch.setenv("LLM_BASE_URL", "https://gw.example/v1")
    assert dub_local._tts_order() == ["gateway", "gemini"]
    monkeypatch.delenv("LLM_BASE_URL")
    assert dub_local._tts_order() == ["gemini"]


def test_tts_order_can_be_pinned(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://gw.example/v1")
    monkeypatch.setenv("DUB_TTS", "gemini")
    assert dub_local._tts_order() == ["gemini"]
    monkeypatch.setenv("DUB_TTS", "gateway")
    assert dub_local._tts_order() == ["gateway"]


def test_translation_must_keep_line_count(monkeypatch):
    import llm_backend
    monkeypatch.setattr(llm_backend, "active", lambda: True)
    monkeypatch.setattr(llm_backend, "generate_json", lambda prompt, schema: ({"lines": ["a"]}, None))
    with pytest.raises(dub_local.DubError):
        dub_local.translate_lines(["x", "y"], "vi", "English")


def test_translation_returns_lines_in_order(monkeypatch):
    import llm_backend
    monkeypatch.setattr(llm_backend, "active", lambda: True)
    monkeypatch.setattr(llm_backend, "generate_json",
                        lambda prompt, schema: ({"lines": [" one ", "two"]}, None))
    assert dub_local.translate_lines(["x", "y"], "vi", "English") == ["one", "two"]


def test_fit_never_slows_down_and_caps_speedup(monkeypatch):
    calls = []
    monkeypatch.setattr(dub_local, "_ffmpeg", lambda args: calls.append(args))
    monkeypatch.setattr(dub_local, "_duration", lambda p: 6.0)
    # fits already: plain copy, no tempo filter
    assert dub_local.fit_to_slot("a.wav", 8.0, "b.wav", 1.4) == 6.0
    assert "-filter:a" not in calls[-1]
    # slot of 3s would need 2x; capped at 1.4x
    final = dub_local.fit_to_slot("a.wav", 3.0, "b.wav", 1.4)
    assert "atempo=1.400" in calls[-1]
    assert final == pytest.approx(6.0 / 1.4)
    # mild overrun: exactly the needed factor
    dub_local.fit_to_slot("a.wav", 5.0, "b.wav", 1.4)
    assert "atempo=1.200" in calls[-1]


def test_same_language_is_refused(monkeypatch, tmp_path):
    import transcribe_backends
    monkeypatch.setattr(transcribe_backends, "transcribe_media",
                        lambda p: {"language": "vi", "segments": [{"start": 0, "end": 1, "text": "xin chào"}]})
    with pytest.raises(dub_local.DubError, match="already"):
        dub_local.dub_video("in.mp4", str(tmp_path / "out.mp4"), "vi")


def test_unknown_language_is_refused():
    with pytest.raises(dub_local.DubError):
        dub_local.dub_video("in.mp4", "out.mp4", "xx")
