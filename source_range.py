"""Process only a section of the source (OpusClip's "timeframe" control).

The trimmed file REPLACES the source in place. Everything downstream (clip
times, the clip editor's source monitor and re-renders, /api/source) treats the
file at that path as the whole video, so keeping one file with one timeline is
what makes all of it agree. Times in the delivered clips are therefore relative
to the selected section.
"""

import os
import re
import subprocess

from ffmpeg_utils import QUALITY_FAST, audio_encode_args, video_encode_args

MIN_RANGE_SECONDS = 5.0

_CLOCK = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{1,2}(?:\.\d+)?)$")


class RangeError(ValueError):
    """The requested section is unusable; the message is safe to show a user."""


def parse_time(value):
    """Seconds from ``90``, ``"90.5"``, ``"1:30"`` or ``"1:02:03"``. None for empty."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = float(value)
    else:
        text = str(value).strip()
        match = _CLOCK.match(text)
        if match:
            hours, minutes, secs = match.groups()
            if float(secs) >= 60 or (hours and int(minutes) >= 60):
                raise RangeError(f"'{text}' is not a valid time.")
            seconds = int(hours or 0) * 3600 + int(minutes) * 60 + float(secs)
        else:
            try:
                seconds = float(text)
            except ValueError:
                raise RangeError(f"'{text}' is not a valid time (use seconds or mm:ss).")
    if seconds < 0 or seconds != seconds or seconds == float("inf"):
        raise RangeError("Times must be zero or positive.")
    return seconds


def normalise(start, end):
    """Validate a (start, end) pair. Either may be None; returns floats or None."""
    s, e = parse_time(start), parse_time(end)
    if s is None and e is None:
        return None, None
    if s is not None and e is not None and e - s < MIN_RANGE_SECONDS:
        raise RangeError(f"The selected section must be at least {int(MIN_RANGE_SECONDS)} seconds long.")
    return s, e


def _duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, timeout=60)
    return float(out.stdout.decode().strip() or 0)


def trim_in_place(path, start, end):
    """Cut ``path`` down to [start, end] (seconds; None = the file's own edge).

    Returns (new_start, new_end, new_duration) actually applied after clamping to
    the file. Raises RangeError when nothing usable would be left. The original
    is untouched until the new file exists and is verified.
    """
    total = _duration(path)
    start = 0.0 if start is None else float(start)
    end = total if end is None else min(float(end), total)
    if total and start >= total - 1:
        raise RangeError("The selected section starts after the end of the video.")
    if end - start < MIN_RANGE_SECONDS:
        raise RangeError(f"The selected section must be at least {int(MIN_RANGE_SECONDS)} seconds long.")
    if start <= 0.05 and end >= total - 0.05:
        return 0.0, total, total          # the whole file: nothing to do

    tmp = path + ".range.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", path,
           "-t", f"{end - start:.3f}", *video_encode_args(QUALITY_FAST),
           *audio_encode_args(), "-movflags", "+faststart", tmp]
    result = subprocess.run(cmd, capture_output=True, timeout=3600)
    if result.returncode != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) == 0:
        if os.path.exists(tmp):
            os.remove(tmp)
        err = (result.stderr or b"").decode(errors="ignore")[-300:]
        raise RuntimeError(f"Could not cut the selected section: {err}")
    new_duration = _duration(tmp)
    if new_duration < MIN_RANGE_SECONDS - 0.5:
        os.remove(tmp)
        raise RangeError("The selected section is too short once cut.")
    os.replace(tmp, path)
    return start, end, new_duration
