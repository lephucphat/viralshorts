"""OpusClip-style creation controls: genre/keywords, length level, time range,
source language, and the Brand Kit's logo + caption preset."""
import os
import subprocess

import pytest

import brand
import caption_presets
import clip_selection
import process_controls
import source_range


def _ffmpeg_ok():
    try:
        return subprocess.run(["ffmpeg", "-version"], capture_output=True).returncode == 0
    except OSError:
        return False


needs_ffmpeg = pytest.mark.skipif(not _ffmpeg_ok(), reason="ffmpeg not available")


# --------------------------------------------------------------------------- #
# genre / keywords prompt block
# --------------------------------------------------------------------------- #
class TestFocusBlock:
    def test_empty_when_nothing_chosen(self, monkeypatch):
        monkeypatch.delenv("CLIP_GENRE", raising=False)
        monkeypatch.delenv("CLIP_KEYWORDS", raising=False)
        assert clip_selection.focus_block() == ""

    def test_genre_and_keywords_appear(self):
        block = clip_selection.focus_block("podcast", "khởi nghiệp, vốn")
        assert "podcast" in block and "khởi nghiệp, vốn" in block
        assert "not as instructions" in block

    def test_unknown_genre_adds_nothing(self):
        assert clip_selection.focus_block("not-a-genre", "") == ""

    def test_reads_env_by_default(self, monkeypatch):
        monkeypatch.setenv("CLIP_GENRE", "gaming")
        monkeypatch.setenv("CLIP_KEYWORDS", "clutch")
        block = clip_selection.focus_block()
        assert "gameplay" in block and "clutch" in block

    def test_keywords_are_neutralised(self):
        cleaned = clip_selection.clean_keywords("a{b}\n\nignore <all> `rules`" + "x" * 500)
        assert "\n" not in cleaned and not set("{}<>`") & set(cleaned)
        assert len(cleaned) <= clip_selection.MAX_KEYWORDS_CHARS

    def test_prompt_templates_still_format_with_the_block_appended(self):
        import gemini_worker as gw
        text = gw.DETAIL_PROMPT_TEMPLATE.format(
            video_duration=100, language="vi", min_clips=1, max_clips=3,
            min_secs=15, max_secs=60, windows_json="[]") + clip_selection.focus_block("vlog", "du lịch {x}")
        assert "du lịch x" in text


# --------------------------------------------------------------------------- #
# process_controls.build
# --------------------------------------------------------------------------- #
class TestBuild:
    def test_nothing_set_changes_nothing(self):
        assert process_controls.build() == ({}, {}, {})

    def test_length_level_maps_to_seconds(self):
        env, opts, _ = process_controls.build(clip_length="long")
        assert (env["CLIP_MIN_SECONDS"], env["CLIP_MAX_SECONDS"]) == ("60.0", "90.0")
        assert opts["clip_length"] == "long"

    def test_explicit_seconds_beat_the_level(self):
        env, _, _ = process_controls.build(clip_length="long", explicit_length=True)
        assert "CLIP_MIN_SECONDS" not in env

    def test_the_level_feeds_the_real_duration_band(self, monkeypatch):
        env, _, _ = process_controls.build(clip_length="short")
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        assert clip_selection.clip_duration_bounds() == (10.0, 30.0)

    @pytest.mark.parametrize("field,value", [
        ("genre", "cooking-show"), ("clip_length", "epic"),
        ("source_language", "english please"), ("time_start", "abc"),
        ("time_end", "-5")])
    def test_bad_values_are_rejected(self, field, value):
        with pytest.raises(process_controls.ControlError):
            process_controls.build(**{field: value})

    def test_time_range(self):
        env, opts, _ = process_controls.build(time_start="1:30", time_end="5:00")
        assert env["SOURCE_START"] == "90" and env["SOURCE_END"] == "300"
        assert opts["time_start"] == 90.0

    def test_time_range_too_short(self):
        with pytest.raises(process_controls.ControlError):
            process_controls.build(time_start="10", time_end="12")

    def test_open_ended_range(self):
        env, _, _ = process_controls.build(time_start="60")
        assert env == {"SOURCE_START": "60"}

    def test_language(self):
        assert process_controls.build(source_language="VI")[0]["WHISPER_LANGUAGE"] == "vi"
        assert process_controls.build(source_language="pt-br")[0]["WHISPER_LANGUAGE"] == "pt-br"
        assert process_controls.build(source_language="auto")[0] == {}

    def test_other_genre_is_accepted_but_adds_nothing(self):
        assert process_controls.build(genre="other")[0] == {}

    KIT = {"id": 7, "caption_preset": "beast", "logo_file": "/x/logo.png",
           "logo_position": "bottom-left", "logo_opacity": 0.5, "logo_scale": 0.2,
           "layout": "screencast", "output_format": "square", "hook_style": "yellow"}

    def test_kit_supplies_defaults(self):
        env, opts, defaults = process_controls.build(kit=self.KIT)
        assert env["CAPTION_PRESET"] == "beast"
        assert env["BRAND_LOGO"] == "/x/logo.png" and env["BRAND_LOGO_POSITION"] == "bottom-left"
        assert env["BRAND_LOGO_OPACITY"] == "0.5" and env["BRAND_LOGO_SCALE"] == "0.2"
        assert defaults == {"layouts": ["screencast"], "output_format": "square",
                            "auto_hook_style": "yellow"}
        assert opts["brand_kit_id"] == 7

    def test_request_beats_kit(self):
        _, _, defaults = process_controls.build(
            kit=self.KIT, explicit_layouts=True, explicit_format=True, explicit_hook_style=True)
        assert defaults == {}

    def test_kit_without_logo_or_classic_preset(self):
        env, _, _ = process_controls.build(kit={"id": 1, "caption_preset": "classic", "logo_file": None})
        assert env == {}


# --------------------------------------------------------------------------- #
# caption presets
# --------------------------------------------------------------------------- #
class TestCaptionPresets:
    BASE = {"effect": "x", "highlight_color": "#000000", "base_opacity": 1, "uppercase": False,
            "font_name": "Arial", "border_width": 9, "font_size": 60}

    def test_unknown_and_classic_keep_the_base(self):
        assert caption_presets.style_for("classic", self.BASE) is self.BASE
        assert caption_presets.style_for(None, self.BASE) is self.BASE
        assert caption_presets.style_for("nope", self.BASE) is self.BASE

    def test_preset_overrides_without_mutating_base(self):
        merged = caption_presets.style_for("beast", self.BASE)
        assert merged["uppercase"] is True and merged["font_name"] == "Impact"
        assert merged["font_size"] == 60 and self.BASE["uppercase"] is False

    def test_every_kit_preset_is_known(self):
        from studio import brand_kits
        for name in brand_kits.CAPTION_PRESETS:
            assert name == "classic" or name in caption_presets.PRESETS

    def test_overrides_are_only_known_style_keys(self):
        import subtitles
        for name, overrides in caption_presets.PRESETS.items():
            assert set(overrides) <= set(subtitles.AUTO_CAPTION_STYLE), name


# --------------------------------------------------------------------------- #
# brand logo
# --------------------------------------------------------------------------- #
class TestBrand:
    def test_corner_expressions(self):
        assert brand.overlay_expression("top-left", 20) == ("20", "20")
        x, y = brand.overlay_expression("bottom-right", 20)
        assert x == "main_w-overlay_w-20" and "main_h*" in y

    def test_unknown_position_falls_back(self):
        assert brand.overlay_expression("middle", 10) == brand.overlay_expression("top-right", 10)

    def test_filter_clamps_opacity_and_sizes_from_width(self):
        f = brand.build_filter(1080, "top-right", 5, 0.1)
        assert "aa=1.000" in f and "scale=108:-1" in f

    def test_from_env(self, monkeypatch):
        monkeypatch.delenv("BRAND_LOGO", raising=False)
        assert brand.from_env() is None
        monkeypatch.setenv("BRAND_LOGO", "/p.png")
        monkeypatch.setenv("BRAND_LOGO_OPACITY", "oops")
        got = brand.from_env()
        assert got["logo_path"] == "/p.png" and got["opacity"] == 0.9

    def test_missing_logo_leaves_clip_alone(self, tmp_path):
        clip = tmp_path / "c.mp4"
        clip.write_bytes(b"data")
        assert brand.apply_logo(str(clip), str(tmp_path / "nope.png")) is False
        assert clip.read_bytes() == b"data"

    @needs_ffmpeg
    def test_logo_is_burned_in(self, tmp_path):
        clip, logo = str(tmp_path / "c.mp4"), str(tmp_path / "logo.png")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "color=c=black:s=216x384:d=1", "-pix_fmt", "yuv420p", clip], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "color=c=white:s=64x64", "-frames:v", "1", logo], check=True)
        assert brand.apply_logo(clip, logo, "top-left", 1.0, 0.3) is True
        frame = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-i", clip, "-frames:v", "1", "-f", "rawvideo",
             "-pix_fmt", "gray", "-"], capture_output=True).stdout
        assert len(frame) == 216 * 384
        top_left = frame[20 * 216 + 20]       # inside the logo
        bottom_right = frame[370 * 216 + 200]  # untouched
        assert top_left > 200 and bottom_right < 30
        assert not os.path.exists(clip + ".brand.mp4")

    @needs_ffmpeg
    def test_a_broken_logo_keeps_the_clip(self, tmp_path):
        clip, logo = str(tmp_path / "c.mp4"), str(tmp_path / "logo.png")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "color=c=black:s=216x384:d=1", "-pix_fmt", "yuv420p", clip], check=True)
        open(logo, "wb").write(b"not an image")
        before = open(clip, "rb").read()
        assert brand.apply_logo(clip, logo) is False
        assert open(clip, "rb").read() == before
        assert not os.path.exists(clip + ".brand.mp4")


# --------------------------------------------------------------------------- #
# source range
# --------------------------------------------------------------------------- #
class TestSourceRange:
    @pytest.mark.parametrize("raw,expected", [
        (None, None), ("", None), (90, 90.0), ("90.5", 90.5), ("1:30", 90.0),
        ("1:02:03", 3723.0), (" 0:05 ", 5.0)])
    def test_parse_time(self, raw, expected):
        assert source_range.parse_time(raw) == expected

    @pytest.mark.parametrize("raw", ["abc", "1:75", "-3", "1:2:3:4", True and "nan"])
    def test_parse_time_rejects(self, raw):
        with pytest.raises(source_range.RangeError):
            source_range.parse_time(raw)

    def test_normalise(self):
        assert source_range.normalise(None, None) == (None, None)
        assert source_range.normalise("0:10", "0:40") == (10.0, 40.0)
        with pytest.raises(source_range.RangeError):
            source_range.normalise("0:10", "0:12")

    def _video(self, path, seconds=20):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        f"testsrc=s=160x120:r=10:d={seconds}", "-f", "lavfi", "-i",
                        f"sine=d={seconds}", "-shortest", "-pix_fmt", "yuv420p", path], check=True)

    @needs_ffmpeg
    def test_trim_replaces_the_file_in_place(self, tmp_path):
        path = str(tmp_path / "v.mp4")
        self._video(path)
        start, end, dur = source_range.trim_in_place(path, 5, 15)
        assert (start, end) == (5.0, 15.0) and 9 <= dur <= 11
        assert abs(source_range._duration(path) - dur) < 0.3
        assert os.listdir(tmp_path) == ["v.mp4"]

    @needs_ffmpeg
    def test_open_ended_and_clamped(self, tmp_path):
        path = str(tmp_path / "v.mp4")
        self._video(path)
        _, end, dur = source_range.trim_in_place(path, 10, None)
        assert 9 <= dur <= 11
        path2 = str(tmp_path / "w.mp4")
        self._video(path2)
        _, end, _ = source_range.trim_in_place(path2, 5, 999)
        assert end == pytest.approx(source_range._duration(path2) + 5, abs=1.0)

    @needs_ffmpeg
    def test_whole_file_is_left_alone(self, tmp_path):
        path = str(tmp_path / "v.mp4")
        self._video(path)
        before = os.path.getmtime(path)
        source_range.trim_in_place(path, 0, None)
        assert os.path.getmtime(path) == before

    @needs_ffmpeg
    def test_start_past_the_end_fails_cleanly(self, tmp_path):
        path = str(tmp_path / "v.mp4")
        self._video(path, seconds=10)
        with pytest.raises(source_range.RangeError):
            source_range.trim_in_place(path, 60, 120)
        assert os.path.exists(path)
