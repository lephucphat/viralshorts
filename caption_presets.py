"""Caption presets the Brand Kit can choose for the automatic captions.

Mirrors the presets in dashboard/src/components/SubtitleModal.jsx
(CAPTION_PRESETS) so a clip captioned automatically with a kit's preset looks
the same as one the user styles by hand. ``classic`` is the plain look and means
"keep the deployment default".
"""

# preset -> overrides applied on top of subtitles.AUTO_CAPTION_STYLE
PRESETS = {
    "tiktok":   {"effect": "none", "highlight_color": "#FE2C55", "base_opacity": 0.75, "uppercase": False, "font_name": "Verdana", "border_width": 2},
    "reels":    {"effect": "none", "highlight_color": "#E1306C", "base_opacity": 0.7,  "uppercase": False, "font_name": "Verdana", "border_width": 2},
    "shorts":   {"effect": "pop",  "highlight_color": "#FF0000", "base_opacity": 0.7,  "uppercase": False, "font_name": "Verdana", "border_width": 2},
    "gold":     {"effect": "glow", "highlight_color": "#FFD700", "base_opacity": 0.6,  "uppercase": False, "font_name": "Verdana", "border_width": 2},
    "neon":     {"effect": "glow", "highlight_color": "#00FF88", "base_opacity": 0.55, "uppercase": False, "font_name": "Verdana", "border_width": 2},
    "cyber":    {"effect": "glow", "highlight_color": "#00FFFF", "base_opacity": 0.5,  "uppercase": False, "font_name": "Verdana", "border_width": 2},
    "karaoke":  {"effect": "none", "highlight_color": "#FF6B6B", "base_opacity": 0.6,  "uppercase": False, "font_name": "Verdana", "border_width": 2},
    "minimal":  {"effect": "none", "highlight_color": "#FFFFFF", "base_opacity": 0.65, "uppercase": False, "font_name": "Verdana", "border_width": 1},
    "beast":    {"effect": "pop",  "highlight_color": "#FFD700", "base_opacity": 1.0,  "uppercase": True,  "font_name": "Impact",  "border_width": 3},
    "boxed":    {"effect": "box",  "highlight_color": "#7C3AED", "base_opacity": 0.85, "uppercase": False, "font_name": "Verdana", "border_width": 2},
}


def style_for(preset, base):
    """``base`` with the preset's overrides applied; ``base`` itself for unknown/classic."""
    overrides = PRESETS.get((preset or "").strip().lower())
    if not overrides:
        return base
    merged = dict(base)
    merged.update(overrides)
    return merged
