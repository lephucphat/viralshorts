"""Low-cost voice dubbing: our own pipeline instead of ElevenLabs' per-minute dubbing API.

    transcribe (local Whisper) -> translate (LLM) -> text-to-speech -> mix over the clip

Why: ElevenLabs bills dubbing per minute of video. The pieces here are either free
(Whisper runs on the machine, Gemini TTS has a free tier) or priced per character /
per token (the OpenAI-compatible gateway in ``LLM_BASE_URL``), which is a small
fraction of that.

Engine choice lives in app.py (``DUBBING_ENGINE=local|elevenlabs``). This module
never imports ``cloud/``.

Env:
  DUB_TTS            "auto" (default) | "gateway" | "gemini"
                     auto = gateway TTS when ``LLM_BASE_URL`` is set, else Gemini; a
                     failing provider falls back to the other when it is configured.
  DUB_TTS_MODEL      gateway TTS model id (default Speakvela/ElevenLabs-TTS)
  DUB_TTS_VOICE      gateway voice name (default alloy)
  DUB_GEMINI_VOICE   Gemini prebuilt voice (default Kore)
  DUB_GEMINI_TTS_MODEL  default gemini-2.5-flash-preview-tts
  DUB_MAX_SPEEDUP    cap on how much a line may be sped up to fit its slot (default 1.4)
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import tempfile
from typing import List, Optional

import httpx
from pydantic import BaseModel

from translate import SUPPORTED_LANGUAGES

_TTS_TIMEOUT = 90.0
GEMINI_API = "https://generativelanguage.googleapis.com/v1beta"


class DubError(Exception):
    pass


class _Lines(BaseModel):
    lines: List[str]


# ---- translation ---------------------------------------------------------------------
def _translate_prompt(texts: List[str], source: Optional[str], target_name: str) -> str:
    src = f"from {source} " if source else ""
    numbered = json.dumps(texts, ensure_ascii=False)
    return (
        f"Translate these spoken subtitle lines {src}into {target_name} for voice-over dubbing.\n"
        "Rules: keep the meaning and a natural spoken tone; keep each line about as long as the "
        "original when spoken aloud (it must fit the same time slot); do not merge, split, add or "
        "drop lines; no notes.\n"
        f"Return JSON {{\"lines\": [...]}} with exactly {len(texts)} strings in the same order.\n"
        f"Input lines: {numbered}"
    )


def translate_lines(texts: List[str], source: Optional[str], target_name: str) -> List[str]:
    import llm_backend

    prompt = _translate_prompt(texts, source, target_name)
    if llm_backend.active():
        parsed, _ = llm_backend.generate_json(prompt, _Lines)
        out = parsed.get("lines") or []
    else:
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            raise DubError("No translation model configured (set LLM_BASE_URL or GEMINI_API_KEY).")
        model = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
        r = httpx.post(
            f"{GEMINI_API}/models/{model}:generateContent",
            headers={"x-goog-api-key": key},
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"responseMimeType": "application/json"}},
            timeout=60,
        )
        if r.status_code >= 400:
            raise DubError(f"Translation failed ({r.status_code})")
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        out = json.loads(text).get("lines") or []
    if len(out) != len(texts):
        raise DubError(f"Translation returned {len(out)} lines for {len(texts)}")
    return [str(x).strip() for x in out]


# ---- text to speech ------------------------------------------------------------------
def _tts_gateway(text: str, dest_mp3: str) -> None:
    base = (os.environ.get("LLM_BASE_URL") or "").strip().rstrip("/")
    key = (os.environ.get("LLM_API_KEY") or "").strip()
    if not base:
        raise DubError("gateway TTS not configured")
    r = httpx.post(
        f"{base}/audio/speech",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": os.environ.get("DUB_TTS_MODEL", "Speakvela/ElevenLabs-TTS"),
              "input": text, "voice": os.environ.get("DUB_TTS_VOICE", "alloy")},
        timeout=_TTS_TIMEOUT,
    )
    if r.status_code != 200 or len(r.content) < 500:
        raise DubError(f"gateway TTS failed ({r.status_code})")
    with open(dest_mp3, "wb") as f:
        f.write(r.content)


def _tts_gemini(text: str, dest_wav: str) -> None:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise DubError("Gemini TTS not configured")
    model = os.environ.get("DUB_GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
    r = httpx.post(
        f"{GEMINI_API}/models/{model}:generateContent",
        headers={"x-goog-api-key": key},
        json={"contents": [{"parts": [{"text": text}]}],
              "generationConfig": {
                  "responseModalities": ["AUDIO"],
                  "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {
                      "voiceName": os.environ.get("DUB_GEMINI_VOICE", "Kore")}}}}},
        timeout=_TTS_TIMEOUT,
    )
    if r.status_code != 200:
        raise DubError(f"Gemini TTS failed ({r.status_code}): {' '.join(r.text.split())[:220]}")
    try:
        part = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
        pcm = base64.b64decode(part["data"])
    except (KeyError, IndexError, ValueError) as e:
        raise DubError("Gemini TTS returned no audio") from e
    raw = dest_wav + ".pcm"
    with open(raw, "wb") as f:
        f.write(pcm)
    _ffmpeg(["-f", "s16le", "-ar", "24000", "-ac", "1", "-i", raw, dest_wav])
    os.remove(raw)


def _tts_order() -> List[str]:
    mode = os.environ.get("DUB_TTS", "auto").strip().lower()
    has_gateway = bool((os.environ.get("LLM_BASE_URL") or "").strip())
    if mode == "gemini":
        return ["gemini"]
    if mode == "gateway":
        return ["gateway"]
    return ["gateway", "gemini"] if has_gateway else ["gemini"]


def synthesize(text: str, dest_wav: str) -> None:
    """One line of speech into a WAV file, trying providers in order."""
    last: Optional[Exception] = None
    for provider in _tts_order():
        try:
            if provider == "gateway":
                tmp = dest_wav + ".mp3"
                _tts_gateway(text, tmp)
                _ffmpeg(["-i", tmp, dest_wav])
                os.remove(tmp)
            else:
                _tts_gemini(text, dest_wav)
            return
        except Exception as e:  # noqa: BLE001 - try the next provider
            last = e
    raise DubError(f"Text-to-speech failed: {last}")


# ---- audio plumbing ------------------------------------------------------------------
def _ffmpeg(args: List[str]) -> None:
    p = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise DubError(f"ffmpeg failed: {p.stderr[-300:]}")


def _duration(path: str) -> float:
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nk=1:nw=1", path], capture_output=True, text=True)
    try:
        return float(p.stdout.strip())
    except ValueError:
        return 0.0


def _atempo_chain(factor: float) -> str:
    """ffmpeg atempo only accepts 0.5-2.0 per stage; we never ask for more than that."""
    return f"atempo={factor:.3f}"


def fit_to_slot(wav: str, slot: float, out_wav: str, max_speedup: float) -> float:
    """Speed a line up (never down) so it fits ``slot`` seconds; returns its final length."""
    length = _duration(wav)
    if slot <= 0 or length <= slot or length <= 0:
        _ffmpeg(["-i", wav, out_wav])
        return length
    factor = min(length / slot, max_speedup)
    _ffmpeg(["-i", wav, "-filter:a", _atempo_chain(factor), out_wav])
    return length / factor


def _has_audio(path: str) -> bool:
    p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                        "stream=index", "-of", "csv=p=0", path], capture_output=True, text=True)
    return bool(p.stdout.strip())


def mix_dub(video_path: str, pieces: List[tuple], output_path: str) -> None:
    """Lay each (start_seconds, wav) over the clip; the original is ducked under speech."""
    inputs = ["-i", video_path]
    chains = []
    labels = []
    for i, (start, wav) in enumerate(pieces, start=1):
        inputs += ["-i", wav]
        ms = max(int(start * 1000), 0)
        chains.append(f"[{i}:a]aformat=sample_rates=44100:channel_layouts=stereo,"
                      f"adelay={ms}|{ms}[d{i}]")
        labels.append(f"[d{i}]")
    chains.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest,"
                  "apad[dubsum]")
    chains.append("[dubsum]asplit=2[dub_a][dub_b]")
    if _has_audio(video_path):
        chains.append("[0:a]aformat=sample_rates=44100:channel_layouts=stereo[orig]")
        chains.append("[orig][dub_a]sidechaincompress=threshold=0.015:ratio=20:attack=5:"
                      "release=350:makeup=1[ducked]")
        chains.append("[ducked][dub_b]amix=inputs=2:normalize=0:duration=first[aout]")
    else:
        chains.append("[dub_a][dub_b]amix=inputs=2:normalize=0:duration=first[aout]")
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(";\n".join(chains))
        script = f.name
    try:
        _ffmpeg([*inputs, "-filter_complex_script", script, "-map", "0:v:0", "-map", "[aout]",
                 "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", output_path])
    finally:
        os.remove(script)


# ---- the pipeline --------------------------------------------------------------------
def dub_video(video_path: str, output_path: str, target_language: str,
              source_language: Optional[str] = None, progress=print) -> str:
    """Dub ``video_path`` into ``target_language`` and write ``output_path``."""
    from transcribe_backends import transcribe_media

    target_name = SUPPORTED_LANGUAGES.get(target_language)
    if not target_name:
        raise DubError(f"Unsupported language: {target_language}")
    max_speedup = float(os.environ.get("DUB_MAX_SPEEDUP", "1.4") or 1.4)

    progress("[dub] transcribing")
    transcript = transcribe_media(video_path)
    segs = [s for s in transcript.get("segments", []) if (s.get("text") or "").strip()]
    if not segs:
        raise DubError("No speech found to dub")
    src = source_language or transcript.get("language")
    if src and src.split("-")[0] == target_language.split("-")[0]:
        raise DubError("The clip is already in that language")

    progress("[dub] translating")
    texts = [re.sub(r"\s+", " ", s["text"]).strip() for s in segs]
    translated = translate_lines(texts, src, target_name)

    pieces = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, (seg, line) in enumerate(zip(segs, translated)):
            if not line:
                continue
            progress(f"[dub] voice {i + 1}/{len(segs)}")
            raw = os.path.join(tmp, f"raw{i}.wav")
            fit = os.path.join(tmp, f"fit{i}.wav")
            synthesize(line, raw)
            start = float(seg["start"])
            nxt = float(segs[i + 1]["start"]) if i + 1 < len(segs) else float(seg["end"]) + 1.0
            fit_to_slot(raw, max(nxt - start - 0.05, float(seg["end"]) - start), fit, max_speedup)
            pieces.append((start, fit))
        if not pieces:
            raise DubError("Nothing to dub")
        progress("[dub] mixing")
        mix_dub(video_path, pieces, output_path)
    return output_path
