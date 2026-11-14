"""WHISPER_LANGUAGE pins the transcription language; unset means auto-detect."""
import pytest

subtitles = pytest.importorskip("subtitles")
transcribe_backends = pytest.importorskip("transcribe_backends")


@pytest.mark.parametrize("raw,expected", [
    ("", None), ("  ", None), ("auto", None), ("AUTO", None),
    ("vi", "vi"), (" VI ", "vi"),
])
def test_get_whisper_language(monkeypatch, raw, expected):
    monkeypatch.setenv("WHISPER_LANGUAGE", raw)
    assert subtitles.get_whisper_language() == expected


def test_unset_is_none(monkeypatch):
    monkeypatch.delenv("WHISPER_LANGUAGE", raising=False)
    assert subtitles.get_whisper_language() is None


class _FakeModel:
    def __init__(self):
        self.kwargs = None

    def transcribe(self, path, **kwargs):
        self.kwargs = kwargs
        info = type("Info", (), {"duration": 0, "language": "vi"})()
        return iter([]), info


def test_language_reaches_faster_whisper(monkeypatch):
    model = _FakeModel()
    monkeypatch.setattr(transcribe_backends, "_get_whisper_model", lambda: (model, "cpu"))
    monkeypatch.setenv("WHISPER_LANGUAGE", "vi")
    transcribe_backends._run_whisper_once("x.wav", beam_size=5)
    assert model.kwargs["language"] == "vi"

    monkeypatch.delenv("WHISPER_LANGUAGE")
    transcribe_backends._run_whisper_once("x.wav", beam_size=5)
    assert "language" not in model.kwargs
