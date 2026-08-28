"""Caption style variants.

Defines experimentable caption styles: minimal, bold-keyword, phrase-reveal, etc.
"""
from __future__ import annotations

from enum import Enum
from typing import Any


class CaptionStyle(str, Enum):
    """Experimentable caption style variants."""
    MINIMAL = "minimal"
    BOLD_KEYWORD = "bold_keyword"
    PHRASE_REVEAL = "phrase_reveal"
    HIGHLIGHT_BOX = "highlight_box"
    KINETIC = "kinetic"


STYLE_CONFIGS: dict[str, dict[str, Any]] = {
    CaptionStyle.MINIMAL.value: {
        "font": "Arial",
        "font_size": 48,
        "color": "#FFFFFF",
        "outline_color": "#000000",
        "outline_width": 2,
        "position": "bottom_center",
        "max_lines": 2,
    },
    CaptionStyle.BOLD_KEYWORD.value: {
        "font": "Arial Bold",
        "font_size": 52,
        "color": "#FFFFFF",
        "keyword_color": "#FFD700",
        "outline_color": "#000000",
        "outline_width": 3,
        "position": "bottom_center",
        "max_lines": 2,
    },
    CaptionStyle.PHRASE_REVEAL.value: {
        "font": "Arial",
        "font_size": 48,
        "color": "#FFFFFF",
        "reveal_animation": "fade_in",
        "outline_color": "#000000",
        "outline_width": 2,
        "position": "bottom_center",
        "max_lines": 2,
    },
    CaptionStyle.HIGHLIGHT_BOX.value: {
        "font": "Arial Bold",
        "font_size": 50,
        "color": "#FFFFFF",
        "background_color": "#000000AA",
        "border_radius": 8,
        "position": "bottom_center",
        "max_lines": 2,
    },
    CaptionStyle.KINETIC.value: {
        "font": "Impact",
        "font_size": 64,
        "color": "#FFFFFF",
        "outline_color": "#000000",
        "outline_width": 4,
        "position": "center",
        "max_lines": 1,
        "animation": "pop_in",
    },
}


def get_style_config(style: CaptionStyle) -> dict[str, Any]:
    """Get the configuration for a caption style."""
    return STYLE_CONFIGS.get(style.value, STYLE_CONFIGS[CaptionStyle.MINIMAL.value])
