"""Small ffmpeg helpers for the project library (cover image)."""

import os
import subprocess


def make_cover(clip_path: str, out_path: str, width: int = 360) -> bool:
    """Write a JPEG still from ``clip_path`` to ``out_path``. True on success.

    Takes a frame one second in (the very first frame is often a fade or black),
    falling back to the first frame for clips shorter than that.
    """
    for seek in ("1", "0"):
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-ss", seek, "-i", clip_path,
                 "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "4", out_path],
                capture_output=True, timeout=60, check=True)
            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                return True
        except Exception:
            continue
    return False
