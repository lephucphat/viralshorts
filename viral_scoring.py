"""Explainable viral score for a proposed clip (ViralShort).

The LLM already hands every clip a single ``predicted_score``. That number is
opaque: you cannot tell *why* a clip got 82, and a small local model tends to
give everything 80. This module adds a second opinion built from signals you
can read off the transcript (and, when the source file is at hand, the audio),
each with its own 0-100 value, and blends it with the LLM score.

``predicted_score`` is never overwritten. ``score_clip`` returns three extra
keys for the clip dict, which ``app.py`` passes through to the dashboard
untouched:

* ``viral_score``      final 0-100 blend
* ``viral_breakdown``  ``{signal: 0-100}`` for every signal that was measurable
* ``viral_reasons``    short codes (``hook_question``, ``pace_fast`` ...) the
                       dashboard maps to labels in the user's language

Everything here is pure functions over ``words`` (``[{'w','s','e'}]``, the same
list ``get_viral_clips`` builds) so it can be unit-tested without media. Audio
is optional and only touched by :func:`audio_signal`.
"""

import os
import re

# --- tuning knobs -----------------------------------------------------------

HOOK_WINDOW = 3.0          # seconds that must grab the viewer
LONG_PAUSE = 0.7           # a gap this long reads as dead air
SPEECH_RATE_BAND = (2.0, 4.8)   # words/second that feel energetic but followable
SWEET_DURATION = (20.0, 45.0)   # seconds; short enough to finish, long enough to land

# Weights of the heuristic signals. Audio is optional: when it was not measured
# the remaining weights are renormalised, so a text-only run is still on 0-100.
WEIGHTS = {
    "hook": 0.35,
    "pace": 0.20,
    "silence": 0.20,
    "length": 0.10,
    "audio": 0.15,
}

# Cues that make the first seconds a question, a claim or a promise. Matched
# against the lower-cased opening text. Vietnamese is first because that is the
# language this fork is tuned for; the English set keeps mixed content working.
_QUESTION_CUES = (
    "tại sao", "vì sao", "làm sao", "làm thế nào", "như thế nào", "bao nhiêu",
    "có bao giờ", "bạn có biết", "ai mà", "cái gì",
    "why ", "how ", "what if", "did you know", "have you ever", "ever wonder",
)
_CLAIM_CUES = (
    "bí mật", "sự thật", "sai lầm", "đừng bao giờ", "không bao giờ", "đừng ",
    "cảnh báo", "sốc", "bất ngờ", "duy nhất", "tuyệt đối", "ngay lập tức",
    "secret", "truth", "mistake", "never ", "stop ", "nobody", "shocking",
    "the biggest", "the only", "worst", "best",
)
_NUMBER = re.compile(r"\d")


def _clamp(value, lo=0.0, hi=100.0):
    return max(lo, min(hi, value))


def clip_words(words, start, end):
    """Words that begin inside ``[start, end)``; ``words`` is sorted by start."""
    return [w for w in words
            if start - 0.01 <= float(w.get("s", 0)) < end]


def _text(words):
    return " ".join(str(w.get("w", "")).strip() for w in words).lower()


# --- individual signals (each returns (score 0-100, reason codes)) ----------

def hook_signal(words, start):
    """How hard the first ``HOOK_WINDOW`` seconds grab: speech begins at once,
    and the opening is a question, a bold claim or a concrete number."""
    opening = [w for w in words
               if start - 0.01 <= float(w.get("s", 0)) < start + HOOK_WINDOW]
    if not opening:
        return 0.0, ["hook_dead_air"]

    score = 0.0
    reasons = []

    lead = float(opening[0].get("s", start)) - start
    if lead <= 0.6:
        score += 30
    elif lead <= 1.5:
        score += 15
        reasons.append("hook_slow_start")
    else:
        reasons.append("hook_slow_start")

    text = _text(opening)
    padded = text + " "  # lets "why " style cues match the last word too
    if "?" in text or any(cue in padded for cue in _QUESTION_CUES):
        score += 30
        reasons.append("hook_question")
    if any(cue in padded for cue in _CLAIM_CUES):
        score += 25
        reasons.append("hook_claim")
    if _NUMBER.search(text):
        score += 15
        reasons.append("hook_number")

    # A real sentence in 3 seconds, not a stammer: reward density a little.
    if len(opening) >= 5:
        score += 10
    return _clamp(score), reasons


def pace_signal(words, start, end):
    """Words per second against the band that feels energetic but followable."""
    duration = max(end - start, 1e-6)
    inside = clip_words(words, start, end)
    rate = len(inside) / duration
    lo, hi = SPEECH_RATE_BAND
    if lo <= rate <= hi:
        return 100.0, ["pace_good"]
    if rate < lo:
        # Falls to 0 at half the lower bound.
        return _clamp(100.0 * (rate - lo / 2) / (lo / 2)), ["pace_slow"]
    return _clamp(100.0 * (hi * 1.6 - rate) / (hi * 0.6)), ["pace_fast"]


def silence_signal(words, start, end):
    """Penalise dead air: the share of the clip spent in pauses over
    ``LONG_PAUSE`` seconds. 25% of the clip silent already scores 0."""
    inside = clip_words(words, start, end)
    duration = max(end - start, 1e-6)
    if len(inside) < 2:
        return 0.0, ["silence_heavy"]
    gaps = 0.0
    for a, b in zip(inside, inside[1:]):
        gap = float(b.get("s", 0)) - float(a.get("e", 0))
        if gap > LONG_PAUSE:
            gaps += gap
    ratio = gaps / duration
    score = 100.0 * (1.0 - min(1.0, ratio / 0.25))
    return _clamp(score), (["silence_heavy"] if ratio > 0.15 else ["silence_tight"])


def length_signal(start, end, bounds=(15.0, 60.0)):
    """Full marks inside the sweet spot, sliding to 40 at the allowed edges."""
    duration = end - start
    lo_b, hi_b = bounds
    lo = max(lo_b, SWEET_DURATION[0])
    hi = min(hi_b, SWEET_DURATION[1])
    if hi < lo:  # a custom band narrower than the sweet spot: any length in it is fine
        return 100.0, ["length_ok"]
    if lo <= duration <= hi:
        return 100.0, ["length_ok"]
    if duration < lo:
        span = max(lo - lo_b, 1e-6)
        return _clamp(40.0 + 60.0 * (duration - lo_b) / span, 0.0, 100.0), ["length_short"]
    span = max(hi_b - hi, 1e-6)
    return _clamp(40.0 + 60.0 * (hi_b - duration) / span, 0.0, 100.0), ["length_long"]


def audio_signal(envelope):
    """Energy dynamics from a peak-normalised RMS envelope (``audio_envelope``):
    a voice that rises and falls holds attention, a flat drone does not.
    Returns ``None`` when there is no audio to judge."""
    if not envelope or len(envelope) < 6:
        return None
    n = len(envelope)
    mean = sum(envelope) / n
    if mean <= 1e-6:
        return None
    var = sum((x - mean) ** 2 for x in envelope) / n
    cv = (var ** 0.5) / mean
    # Count separate bursts above 60% of peak (rising edges only).
    peaks = sum(1 for i in range(1, n) if envelope[i] >= 0.6 and envelope[i - 1] < 0.6)
    score = _clamp(cv / 0.8, 0.0, 1.0) * 70.0 + min(peaks, 6) / 6.0 * 30.0
    return _clamp(score), (["audio_dynamic"] if score >= 55 else ["audio_flat"])


# --- orchestration -----------------------------------------------------------

def blend_weight():
    """Share of the final score that comes from the heuristic (0-1)."""
    try:
        return _clamp(float(os.environ.get("VIRAL_BLEND", "0.4")), 0.0, 1.0)
    except ValueError:
        return 0.4


def score_clip(words, start, end, llm_score=None, envelope=None, bounds=(15.0, 60.0)):
    """Score one clip.

    ``words`` is the whole-video word list; ``start``/``end`` the final
    (already snapped) cut; ``llm_score`` the model's ``predicted_score``;
    ``envelope`` an optional audio envelope for the same span.
    """
    start, end = float(start), float(end)
    breakdown = {}
    reasons = []

    for key, (value, why) in (
        ("hook", hook_signal(words, start)),
        ("pace", pace_signal(words, start, end)),
        ("silence", silence_signal(words, start, end)),
        ("length", length_signal(start, end, bounds)),
    ):
        breakdown[key] = round(value)
        reasons.extend(why)

    audio = audio_signal(envelope)
    if audio is not None:
        breakdown["audio"] = round(audio[0])
        reasons.extend(audio[1])

    total_w = sum(WEIGHTS[k] for k in breakdown)
    heuristic = sum(breakdown[k] * WEIGHTS[k] for k in breakdown) / total_w

    try:
        llm = _clamp(float(llm_score)) if llm_score is not None else None
    except (TypeError, ValueError):
        llm = None

    if llm is None:
        final = heuristic
    else:
        w = blend_weight()
        final = (1.0 - w) * llm + w * heuristic
        breakdown["llm"] = round(llm)

    return {
        "viral_score": int(round(_clamp(final))),
        "viral_breakdown": breakdown,
        "viral_reasons": reasons,
    }


def attach_scores(shorts, words, video_path=None, bounds=(15.0, 60.0)):
    """Add the ``viral_*`` keys to every clip dict, in place.

    Never raises: a failure scoring one clip leaves it with only its LLM score
    rather than failing the job. ``video_path`` enables the audio signal.
    """
    for clip in shorts:
        try:
            start, end = float(clip.get("start", 0)), float(clip.get("end", 0))
            envelope = None
            if video_path:
                try:
                    from active_speaker import audio_envelope
                    envelope = list(audio_envelope(video_path, start, end - start))
                except Exception:
                    envelope = None
            clip.update(score_clip(words, start, end, clip.get("predicted_score"),
                                   envelope=envelope, bounds=bounds))
        except Exception as exc:  # pragma: no cover - defensive
            print(f"   viral score skipped for one clip: {exc}")
    return shorts
