"""viral_scoring: pure functions over the word list, no media needed."""

import pytest

import viral_scoring as vs


def _word(w, s, e):
    return {"w": w, "s": s, "e": e}


def _speech(text, start, per_word=0.3, gap=0.0):
    """Build consecutive words from a sentence starting at ``start``."""
    out, t = [], start
    for token in text.split():
        out.append(_word(" " + token, round(t, 3), round(t + per_word, 3)))
        t += per_word + gap
    return out


class TestHook:
    def test_question_opening_scores_higher_than_flat_opening(self):
        q = _speech("Tại sao bạn không bao giờ giàu được?", 10.0)
        flat = _speech("Hôm nay trời khá là đẹp nhỉ mọi người", 10.0)
        qs, q_why = vs.hook_signal(q, 10.0)
        fs, _ = vs.hook_signal(flat, 10.0)
        assert qs > fs
        assert "hook_question" in q_why

    def test_number_and_claim_are_recognised(self):
        words = _speech("Bí mật 3 bước để kiếm tiền online", 0.0)
        score, why = vs.hook_signal(words, 0.0)
        assert "hook_claim" in why and "hook_number" in why
        assert score > 50

    def test_english_cues_still_work(self):
        words = _speech("Why do 90 percent of people fail at this", 5.0)
        _, why = vs.hook_signal(words, 5.0)
        assert "hook_question" in why

    def test_no_speech_in_first_seconds_is_dead_air(self):
        words = _speech("xin chào mọi người", 20.0)  # starts 10s after the cut
        score, why = vs.hook_signal(words, 10.0)
        assert score == 0.0
        assert why == ["hook_dead_air"]

    def test_slow_start_is_flagged(self):
        words = _speech("chào mọi người hôm nay mình chia sẻ", 11.2)
        _, why = vs.hook_signal(words, 10.0)
        assert "hook_slow_start" in why


class TestPace:
    def test_good_rate_is_full_marks(self):
        words = _speech(" ".join(["a"] * 90), 0.0, per_word=1 / 3.5)  # 3.5 w/s
        score, why = vs.pace_signal(words, 0.0, 26.0)
        assert score == 100.0 and why == ["pace_good"]

    def test_slow_speech_is_penalised(self):
        words = _speech(" ".join(["a"] * 20), 0.0, per_word=0.5)  # ~2 w/s over 30s -> ~0.67
        score, why = vs.pace_signal(words, 0.0, 30.0)
        assert score < 50 and why == ["pace_slow"]

    def test_machine_gun_speech_is_penalised(self):
        words = _speech(" ".join(["a"] * 240), 0.0, per_word=0.1)  # 8 w/s
        score, why = vs.pace_signal(words, 0.0, 30.0)
        assert score < 30 and why == ["pace_fast"]


class TestSilence:
    def test_tight_delivery_scores_full(self):
        words = _speech(" ".join(["a"] * 60), 0.0, per_word=0.3, gap=0.05)
        score, why = vs.silence_signal(words, 0.0, 21.0)
        assert score == 100.0 and why == ["silence_tight"]

    def test_long_pauses_are_penalised(self):
        words = _speech("một hai ba", 0.0) + _speech("bốn năm sáu", 8.0)  # ~7s hole
        score, why = vs.silence_signal(words, 0.0, 10.0)
        assert score == 0.0 and why == ["silence_heavy"]

    def test_too_few_words_counts_as_empty(self):
        score, _ = vs.silence_signal([_word("a", 0, 1)], 0.0, 20.0)
        assert score == 0.0


class TestLength:
    def test_sweet_spot_full_marks(self):
        assert vs.length_signal(0, 30)[0] == 100.0

    def test_edges_slide_to_forty(self):
        assert vs.length_signal(0, 15)[0] == pytest.approx(40.0)
        assert vs.length_signal(0, 60)[0] == pytest.approx(40.0)

    def test_custom_band_inside_sweet_spot_is_always_fine(self):
        assert vs.length_signal(0, 25, bounds=(22, 28))[0] == 100.0


class TestAudio:
    def test_none_without_audio(self):
        assert vs.audio_signal([]) is None
        assert vs.audio_signal([0.0] * 10) is None

    def test_flat_drone_scores_below_dynamic_voice(self):
        flat = [0.5] * 40
        dynamic = [0.2, 0.9, 0.3, 1.0, 0.1, 0.8, 0.2, 0.95] * 5
        assert vs.audio_signal(dynamic)[0] > vs.audio_signal(flat)[0]
        assert "audio_flat" in vs.audio_signal(flat)[1]


class TestScoreClip:
    def _good(self):
        return _speech("Tại sao 90 phần trăm người không bao giờ giàu được "
                       + " ".join(["từ"] * 85), 10.0, per_word=0.28)

    def test_returns_the_three_keys_and_keeps_range(self):
        out = vs.score_clip(self._good(), 10.0, 40.0, llm_score=80)
        assert set(out) == {"viral_score", "viral_breakdown", "viral_reasons"}
        assert 0 <= out["viral_score"] <= 100
        assert out["viral_breakdown"]["llm"] == 80
        assert "audio" not in out["viral_breakdown"]

    def test_blend_follows_viral_blend_env(self, monkeypatch):
        words = self._good()
        monkeypatch.setenv("VIRAL_BLEND", "0")
        assert vs.score_clip(words, 10, 40, llm_score=42)["viral_score"] == 42
        monkeypatch.setenv("VIRAL_BLEND", "1")
        heuristic_only = vs.score_clip(words, 10, 40, llm_score=42)["viral_score"]
        assert heuristic_only != 42

    def test_missing_llm_score_falls_back_to_heuristic(self):
        out = vs.score_clip(self._good(), 10, 40, llm_score=None)
        assert "llm" not in out["viral_breakdown"]
        assert out["viral_score"] > 0

    def test_garbage_llm_score_is_ignored(self):
        out = vs.score_clip(self._good(), 10, 40, llm_score="n/a")
        assert "llm" not in out["viral_breakdown"]

    def test_audio_is_included_when_provided(self):
        env = [0.2, 0.9, 0.3, 1.0, 0.1, 0.8, 0.2, 0.95] * 5
        out = vs.score_clip(self._good(), 10, 40, llm_score=70, envelope=env)
        assert "audio" in out["viral_breakdown"]

    def test_good_clip_beats_bad_clip_at_equal_llm_score(self):
        bad = _speech("ừm thì", 10.0) + _speech("à ừ thì là", 30.0)
        good = vs.score_clip(self._good(), 10, 40, llm_score=75)["viral_score"]
        poor = vs.score_clip(bad, 10, 40, llm_score=75)["viral_score"]
        assert good > poor


class TestAttachScores:
    def test_adds_keys_in_place_without_touching_predicted_score(self):
        words = _speech("Tại sao bạn thất bại? " + " ".join(["từ"] * 80), 0.0, per_word=0.3)
        shorts = [{"start": 0.0, "end": 30.0, "predicted_score": 77}]
        vs.attach_scores(shorts, words)
        assert shorts[0]["predicted_score"] == 77
        assert "viral_score" in shorts[0]

    def test_one_bad_clip_does_not_break_the_rest(self):
        words = _speech(" ".join(["từ"] * 80), 0.0, per_word=0.3)
        shorts = [{"start": "oops", "end": None}, {"start": 0.0, "end": 24.0, "predicted_score": 60}]
        vs.attach_scores(shorts, words)
        assert "viral_score" not in shorts[0]
        assert "viral_score" in shorts[1]


class TestGetViralClipsAddsScore:
    """End to end through main.get_viral_clips with the LLM stubbed out."""

    def _transcript(self):
        segments, t = [], 0.0
        for i in range(8):  # 8 segments of ~15 s of steady speech
            words, seg_start = [], t
            for _ in range(48):
                words.append({"word": " từ", "start": round(t, 3), "end": round(t + 0.28, 3)})
                t += 0.31
            segments.append({"start": seg_start, "end": round(t, 3),
                             "text": " ".join(w["word"].strip() for w in words),
                             "words": words})
        return {"language": "vi", "text": "", "segments": segments}

    def test_every_clip_gets_viral_keys_and_keeps_predicted_score(self, monkeypatch):
        main = pytest.importorskip("main")
        import gemini_worker

        monkeypatch.setattr(main.llm_backend, "active", lambda: True)
        monkeypatch.setattr(main.llm_backend, "model_name", lambda: "stub")

        def fake_stage(client, model, prompt, schema):
            if schema is gemini_worker.ScoreResponse:
                return {"windows": [{"id": "window_001", "start": 0, "end": 90,
                                     "score": 90, "reason": "x"}]}, None
            return {"shorts": [{
                "start": 1.0, "end": 31.0, "source_window_id": "window_001",
                "predicted_score": 72,
                "video_description_for_tiktok": "d", "video_description_for_instagram": "d",
                "video_title_for_youtube_short": "t", "viral_hook_text": "h",
            }]}, None

        monkeypatch.setattr(main, "_run_gemini_stage", fake_stage)
        out = main.get_viral_clips(self._transcript(), 120.0)
        assert out and out["shorts"]
        clip = out["shorts"][0]
        assert clip["predicted_score"] == 72
        assert 0 <= clip["viral_score"] <= 100
        assert clip["viral_breakdown"]["llm"] == 72
        assert clip["viral_reasons"]
