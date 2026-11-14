"""OpusClip-style creation controls for POST /api/process.

Pure functions, no FastAPI: ``build`` turns the request's optional fields (and
the user's Brand Kit, when one applies) into the per-job environment the
``main.py`` subprocess reads, plus the options recorded on the project. Bad
input raises ``ControlError`` with a message safe to show the user; app.py maps
it to a 400.

Precedence, most specific first: a field the caller sent > the Brand Kit's
default > the deployment default. An explicit ``clip_min_seconds`` /
``clip_max_seconds`` beats the ``clip_length`` level.
"""

import re

import caption_presets
import clip_selection
import source_range

LANGUAGE_RE = re.compile(r"^[a-z]{2,3}(-[a-z]{2,4})?$")


class ControlError(ValueError):
    pass


def _text(value):
    return value.strip() if isinstance(value, str) else value


def _seconds(value, name):
    try:
        return source_range.parse_time(value)
    except source_range.RangeError as e:
        raise ControlError(f"{name}: {e}")


def build(genre=None, keywords=None, clip_length=None, time_start=None, time_end=None,
          source_language=None, kit=None, explicit_length=False, explicit_format=False,
          explicit_layouts=False, explicit_hook_style=False):
    """Return ``(env, options, kit_defaults)``.

    ``env`` is merged into the job's environment. ``options`` records what was
    chosen (for the project page). ``kit_defaults`` holds the Brand Kit values
    the caller should apply to its own fields (``layouts``, ``output_format``,
    ``auto_hook_style``) when the request did not set them.
    """
    env, options, kit_defaults = {}, {}, {}

    genre = (_text(genre) or "").lower()
    if genre:
        if genre not in clip_selection.GENRES:
            raise ControlError(f"genre must be one of: {', '.join(clip_selection.GENRES)}")
        if genre != "other":
            env["CLIP_GENRE"] = genre
            options["genre"] = genre

    keywords = clip_selection.clean_keywords(keywords)
    if keywords:
        env["CLIP_KEYWORDS"] = keywords
        options["keywords"] = keywords

    level = (_text(clip_length) or "").lower()
    if level:
        bounds = clip_selection.length_level_bounds(level)
        if bounds is None:
            raise ControlError(f"clip_length must be one of: {', '.join(clip_selection.LENGTH_LEVELS)}")
        options["clip_length"] = level
        if not explicit_length:
            env["CLIP_MIN_SECONDS"], env["CLIP_MAX_SECONDS"] = (str(b) for b in bounds)

    start, end = _seconds(time_start, "time_start"), _seconds(time_end, "time_end")
    try:
        start, end = source_range.normalise(start, end)
    except source_range.RangeError as e:
        raise ControlError(str(e))
    if start is not None:
        env["SOURCE_START"] = f"{start:g}"
        options["time_start"] = start
    if end is not None:
        env["SOURCE_END"] = f"{end:g}"
        options["time_end"] = end

    language = (_text(source_language) or "").lower()
    if language and language != "auto":
        if not LANGUAGE_RE.match(language):
            raise ControlError("source_language must be a language code such as 'vi' or 'en'")
        env["WHISPER_LANGUAGE"] = language
        options["source_language"] = language

    if kit:
        options["brand_kit_id"] = kit.get("id")
        preset = kit.get("caption_preset")
        if preset and preset != "classic" and preset in caption_presets.PRESETS:
            env["CAPTION_PRESET"] = preset
        if kit.get("logo_file"):
            env["BRAND_LOGO"] = kit["logo_file"]
            env["BRAND_LOGO_POSITION"] = str(kit.get("logo_position") or "top-right")
            env["BRAND_LOGO_OPACITY"] = str(kit.get("logo_opacity", 0.9))
            env["BRAND_LOGO_SCALE"] = str(kit.get("logo_scale", 0.14))
        if not explicit_layouts and kit.get("layout"):
            kit_defaults["layouts"] = [kit["layout"]]
        if not explicit_format and kit.get("output_format"):
            kit_defaults["output_format"] = kit["output_format"]
        if not explicit_hook_style and kit.get("hook_style"):
            kit_defaults["auto_hook_style"] = kit["hook_style"]
    return env, options, kit_defaults
