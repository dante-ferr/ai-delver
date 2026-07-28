import colorsys
import hashlib

import customtkinter as ctk

from src.config import config


def _cfg(name: str, default):
    try:
        return getattr(config.RUN_GRID, name)
    except AttributeError:
        return default


def color_for_level_hash(level_hash: str) -> str:
    """Stable pastel-ish color from a level hash."""
    if not level_hash:
        return "#6b7280"
    digest = hashlib.md5(level_hash.encode("utf-8")).hexdigest()
    hue = int(digest[:4], 16) / 65535.0
    sat = 0.52 + (int(digest[4:6], 16) / 255.0) * 0.18
    val = 0.68 + (int(digest[6:8], 16) / 255.0) * 0.14
    r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def resolve_bg_color(widget, fallback: str = "#1f1f1f") -> str:
    mode_index = 0 if ctk.get_appearance_mode() == "Light" else 1
    current = widget
    while current is not None:
        try:
            raw = current.cget("fg_color")
        except Exception:
            break
        if isinstance(raw, (list, tuple)) and len(raw) == 2:
            color = raw[mode_index]
        elif isinstance(raw, str) and " " in raw:
            parts = raw.split()
            color = parts[min(mode_index, len(parts) - 1)]
        else:
            color = raw
        if color and color != "transparent":
            return color
        try:
            current = current.master
        except AttributeError:
            break
    return fallback
