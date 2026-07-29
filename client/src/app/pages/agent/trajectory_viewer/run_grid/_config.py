import colorsys
import hashlib

import customtkinter as ctk

from src.config import config


def _cfg(name: str, default):
    try:
        return getattr(config.RUN_GRID, name)
    except AttributeError:
        return default


from app.theme import theme


def get_color_progression_palette() -> list[str]:
    """Returns a bright, high-contrast color progression palette for the run grid."""
    return [
        theme.primary_color,  # Main Primary Accent
        theme.secondary_color,  # Secondary Accent
        theme.primary_lighter,  # Light Primary
        "#bf7f3f",  # Warm Bronze (Special Group)
        "#f59e0b",  # Amber Gold
        "#10b981",  # Emerald Green
        "#cbaa89",  # Warm Sand (Special Group)
        "#a855f7",  # Royal Purple
        "#fb7185",  # Coral Pink
        "#84cc16",  # Lime Green
        "#3b82f6",  # Ocean Blue
        "#d97706",  # Warm Copper
        "#06b6d4",  # Bright Cyan
        "#d946ef",  # Magenta Fuchsia
        "#14b8a6",  # Jade Teal
        "#eab308",  # Goldenrod
        "#6366f1",  # Indigo
        "#f4a261",  # Warm Peach
        "#38bdf8",  # Sky Blue
        "#22c55e",  # Bright Mint
        "#818cf8",  # Iris Periwinkle
        "#2dd4bf",  # Bright Aqua
        "#ff7043",  # Sunset Orange
    ]


def color_for_level_hash(
    level_hash: str,
    index: int | None = None,
    ordered_hashes: list[str] | None = None,
) -> str:
    """Returns a color from a distinct looping color progression sequence for a given level hash."""
    palette = get_color_progression_palette()
    if not level_hash:
        return theme.bg_mid

    if index is None and ordered_hashes:
        try:
            index = ordered_hashes.index(level_hash)
        except ValueError:
            index = None

    if index is None:
        digest = hashlib.md5(level_hash.encode("utf-8")).hexdigest()
        index = int(digest[:6], 16)

    return palette[index % len(palette)]


def resolve_bg_color(widget, fallback: str | None = None) -> str:
    if fallback is None:
        fallback = theme.bg_darkest
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
