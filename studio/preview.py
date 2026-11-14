"""Source preview: title, cover and length of a pasted link, before any credit is spent.

Only metadata is read (yt-dlp with ``skip_download``); nothing is fetched to disk. The link goes
through ``assert_public_url`` first, so it cannot be used to probe the server's own network.
Results are cached for a few minutes because people paste the same link, edit it, paste it again.
"""

import time
from typing import Callable, Optional

CACHE_SECONDS = 600
CACHE_MAX = 200
_cache: dict = {}


class PreviewError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _default_extract(url: str) -> dict:
    import yt_dlp
    opts = {
        "quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True,
        "socket_timeout": 15, "retries": 1, "cachedir": False, "ignore_no_formats_error": True,
        "extract_flat": "in_playlist",
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False) or {}


def _public(info: dict) -> dict:
    thumb = info.get("thumbnail") or ""
    if not thumb:
        thumbs = [t for t in (info.get("thumbnails") or []) if isinstance(t, dict) and t.get("url")]
        thumb = thumbs[-1]["url"] if thumbs else ""
    if not str(thumb).lower().startswith(("http://", "https://")):
        thumb = ""
    try:
        duration = int(float(info.get("duration") or 0))
    except (TypeError, ValueError):
        duration = 0
    return {
        "title": " ".join(str(info.get("title") or "").split())[:200],
        "channel": " ".join(str(info.get("uploader") or info.get("channel") or "").split())[:120],
        "thumbnail": thumb,
        "duration": max(0, duration),
        "live": bool(info.get("is_live")),
        "site": str(info.get("extractor_key") or info.get("extractor") or "")[:40],
    }


def fetch(url: str, check_url: Optional[Callable[[str], str]] = None,
          extract: Optional[Callable[[str], dict]] = None) -> dict:
    url = (url or "").strip()
    if not url or len(url) > 2000:
        raise PreviewError("bad_url", "Paste a video link.")
    if check_url is not None:
        try:
            check_url(url)
        except Exception:
            raise PreviewError("bad_url", "That link cannot be used.")
    hit = _cache.get(url)
    if hit and hit[0] > time.time():
        return hit[1]
    try:
        info = (extract or _default_extract)(url)
    except Exception:
        raise PreviewError("unavailable", "Could not read that link.")
    if not info.get("title") and not info.get("duration"):
        raise PreviewError("unavailable", "Could not read that link.")
    out = _public(info)
    if len(_cache) >= CACHE_MAX:
        _cache.clear()
    _cache[url] = (time.time() + CACHE_SECONDS, out)
    return out
