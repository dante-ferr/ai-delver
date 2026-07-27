"""Configurable UI fonts — swap family via ``[style.font] family`` in config.toml.

Font files live under ``assets/fonts/<Family>/`` (OFL TTF). Call ``init_fonts()``
once after the CustomTkinter color theme is loaded and before widgets are built.

On Linux, ``bootstrap`` registers those folders with fontconfig before Tk starts.
Windows / macOS register TTFs into the session / user font directory here.

``vertical_scale`` (>1) stretches glyph height without widening advances, so the
face reads taller / less squat.
"""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path
from typing import Literal, Optional, Tuple, Union

import customtkinter as ctk
from customtkinter.windows.widgets.font import FontManager
from customtkinter.windows.widgets.theme import ThemeManager

from bundled_fonts import refresh_fontconfig
from src.config import config

from .font_stretch import scale_font_vertically

_initialized = False

CanvasFont = Union[Tuple[str, int], Tuple[str, int, str]]


def family_name() -> str:
    return str(config.STYLE.FONT.FAMILY)


def vertical_scale() -> float:
    try:
        return float(config.STYLE.FONT.VERTICAL_SCALE)
    except AttributeError:
        return 1.0


def fonts_dir() -> Path:
    return config.ASSETS_PATH / "fonts" / family_name()


def _scaled_family_dir() -> Path:
    from bundled_fonts import fonts_cache_root

    scale = vertical_scale()
    scale_key = f"{scale:.3f}".rstrip("0").rstrip(".")
    return fonts_cache_root() / family_name() / f"v{scale_key}"


def _prepare_family_ttfs() -> Path:
    """Return directory of TTFs to register (source, or vertically stretched cache)."""
    source_dir = fonts_dir()
    scale = vertical_scale()
    if abs(scale - 1.0) < 1e-6:
        return source_dir

    dest_dir = _scaled_family_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    for src in sorted(source_dir.glob("*.ttf")):
        dest = dest_dir / src.name
        # Rebuild when source is newer or cache missing.
        if (
            not dest.exists()
            or dest.stat().st_mtime < src.stat().st_mtime
            or dest.stat().st_size == 0
        ):
            try:
                scale_font_vertically(src, dest, scale)
            except Exception:
                logging.exception("Failed to stretch font %s; using source", src.name)
                shutil.copy2(src, dest)
    return dest_dir


def _install_font_file(font_path: Path) -> bool:
    """Register a TTF so Tk can resolve it by family name (Windows / macOS)."""
    if sys.platform.startswith("win"):
        return FontManager.load_font(str(font_path))

    if sys.platform == "darwin":
        dest_dir = Path.home() / "Library" / "Fonts"
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / font_path.name
            if not dest.exists() or dest.stat().st_size != font_path.stat().st_size:
                shutil.copy2(font_path, dest)
            return True
        except OSError as err:
            logging.warning("Font install failed for %s: %s", font_path.name, err)
            return False

    # Linux: fontconfig is prepared in bootstrap / refreshed below.
    if sys.platform.startswith("linux"):
        return font_path.is_file()

    logging.warning("Unsupported platform for custom fonts: %s", sys.platform)
    return False


def init_fonts() -> None:
    """Ensure the configured family is registered and set as the CTk default."""
    global _initialized
    if _initialized:
        return

    FontManager.init_font_manager()
    source_dir = fonts_dir()
    family = family_name()

    if not source_dir.is_dir():
        # System-installed family (e.g. FiraCode Nerd Font from waybar) — no bundle needed.
        logging.info("Using system font family %r (no assets/fonts/%s/)", family, family)
        if "CTkFont" in ThemeManager.theme:
            ThemeManager.theme["CTkFont"]["family"] = family
        _initialized = True
        return

    active_dir = _prepare_family_ttfs()
    if sys.platform.startswith("linux"):
        # Prefer stretched cache over the stock assets copy of the same family.
        refresh_fontconfig(active_family=family, active_dir=active_dir)

    loaded_any = False
    for path in sorted(active_dir.glob("*.ttf")):
        if _install_font_file(path):
            loaded_any = True
        else:
            logging.warning("Failed to load font file: %s", path)

    if loaded_any and "CTkFont" in ThemeManager.theme:
        ThemeManager.theme["CTkFont"]["family"] = family

    _initialized = True


def app_font(
    size: Optional[int] = None,
    weight: Literal["normal", "bold"] = "normal",
    slant: Literal["italic", "roman"] = "roman",
    underline: bool = False,
    overstrike: bool = False,
) -> ctk.CTkFont:
    """CTk font using the configured family (default size: standard)."""
    if size is None:
        size = int(config.STYLE.FONT.STANDARD_SIZE)
    return ctk.CTkFont(
        family=family_name(),
        size=size,
        weight=weight,
        slant=slant,
        underline=underline,
        overstrike=overstrike,
    )


def canvas_font(size: int, *, bold: bool = False) -> CanvasFont:
    """Tk ``create_text`` font tuple using the configured family."""
    size_i = int(size)
    if bold:
        return (family_name(), size_i, "bold")
    return (family_name(), size_i)
