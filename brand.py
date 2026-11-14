"""Brand logo burned into finished clips (a Brand Kit's logo)."""

import os
import subprocess

from ffmpeg_utils import METADATA_SCRUB, QUALITY, video_encode_args

POSITIONS = ("top-left", "top-right", "bottom-left", "bottom-right")
MARGIN_RATIO = 0.04
# Short-form platforms put their own UI over the very bottom and the right edge
# (caption, buttons). The bottom positions sit above that band instead of in it.
BOTTOM_SAFE_RATIO = 0.16


def overlay_expression(position, margin):
    """The ffmpeg overlay x:y for a corner, as expressions of main_w/h and overlay_w/h."""
    if position not in POSITIONS:
        position = "top-right"
    vertical, horizontal = position.split("-")
    x = f"{margin}" if horizontal == "left" else f"main_w-overlay_w-{margin}"
    if vertical == "top":
        y = f"{margin}"
    else:
        y = f"main_h-overlay_h-(main_h*{BOTTOM_SAFE_RATIO})"
    return x, y


def build_filter(video_width, position, opacity, scale):
    """The filter_complex that scales the logo to ``scale`` of the clip width and overlays it."""
    logo_w = max(48, int(video_width * float(scale)))
    margin = max(8, int(video_width * MARGIN_RATIO))
    x, y = overlay_expression(position, margin)
    opacity = max(0.0, min(1.0, float(opacity)))
    return (f"[1:v]scale={logo_w}:-1,format=rgba,colorchannelmixer=aa={opacity:.3f}[logo];"
            f"[0:v][logo]overlay=x={x}:y={y}")


def _probe_width(video_path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width", "-of", "csv=p=0", video_path], stderr=subprocess.STDOUT, timeout=60)
    return int(out.decode().strip().split(",")[0])


def apply_logo(video_path, logo_path, position="top-right", opacity=0.9, scale=0.14):
    """Burn ``logo_path`` into ``video_path`` in place. True on success.

    A failure leaves the clip exactly as it was: a logo problem must never cost
    the user a clip they already waited for.
    """
    if not logo_path or not os.path.exists(logo_path):
        print(f"   ⚠️ Brand logo missing ({logo_path}); clip kept unbranded.")
        return False
    try:
        width = _probe_width(video_path)
    except Exception as e:
        print(f"   ⚠️ Could not probe clip for the brand logo ({e}); clip kept unbranded.")
        return False
    tmp = video_path + ".brand.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", video_path, "-i", logo_path,
           "-filter_complex", build_filter(width, position, opacity, scale),
           *video_encode_args(QUALITY), "-c:a", "copy", *METADATA_SCRUB,
           "-movflags", "+faststart", tmp]
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=1800)
    if result.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 0:
        os.replace(tmp, video_path)
        return True
    err = (result.stderr or b"").decode(errors="ignore")[-300:]
    print(f"   ⚠️ Brand logo pass failed (clip kept unbranded): {err}")
    if os.path.exists(tmp):
        os.remove(tmp)
    return False


def from_env():
    """The logo settings a job carries in its environment, or None when there is none."""
    path = os.environ.get("BRAND_LOGO", "").strip()
    if not path:
        return None
    def _num(name, default):
        try:
            return float(os.environ.get(name, default))
        except ValueError:
            return float(default)
    return {"logo_path": path,
            "position": os.environ.get("BRAND_LOGO_POSITION", "top-right"),
            "opacity": _num("BRAND_LOGO_OPACITY", 0.9),
            "scale": _num("BRAND_LOGO_SCALE", 0.14)}
