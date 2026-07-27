"""Configurable UI fonts — swap family via ``[style.font] family`` in config.toml.

Font files live under ``assets/fonts/<Family>/`` (OFL TTF), or any system family
(e.g. waybar's ``FiraCode Nerd Font``). Call ``init_fonts()`` once after the
CustomTkinter color theme is loaded and before widgets are built.

``vertical_scale`` stretches glyph height. ``tracking`` < 1.0 tightens advances
(shorter letter spacing). Tuned copies are cached under ``client/data/fonts_cache/``.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Literal, Optional, Tuple, Union

import customtkinter as ctk
from customtkinter.windows.widgets.font import FontManager
from customtkinter.windows.widgets.theme import ThemeManager

from bundled_fonts import fonts_cache_root, refresh_fontconfig
from src.config import config

from .font_stretch import transform_font

_initialized = False

CanvasFont = Union[Tuple[str, int], Tuple[str, int, str]]


def family_name() -> str:
    return str(config.STYLE.FONT.FAMILY)


def vertical_scale() -> float:
    try:
        return float(config.STYLE.FONT.VERTICAL_SCALE)
    except AttributeError:
        return 1.0


def tracking() -> float:
    try:
        return float(config.STYLE.FONT.TRACKING)
    except AttributeError:
        return 1.0


def fonts_dir() -> Path:
    return config.ASSETS_PATH / "fonts" / family_name()


def _needs_transform() -> bool:
    return abs(vertical_scale() - 1.0) >= 1e-6 or abs(tracking() - 1.0) >= 1e-6


def _cache_key() -> str:
    v = f"{vertical_scale():.3f}".rstrip("0").rstrip(".")
    t = f"{tracking():.3f}".rstrip("0").rstrip(".")
    return f"v{v}_t{t}"


def _cache_family_dir() -> Path:
    # Sanitize family for filesystem (spaces ok on Linux; keep readable).
    safe = family_name().replace("/", "_")
    return fonts_cache_root() / safe / _cache_key()


def _system_font_files(family: str) -> list[Path]:
    """Locate installed TTF/OTF files for a fontconfig family."""
    if not sys.platform.startswith("linux"):
        return []
    try:
        result = subprocess.run(
            ["fc-list", f":family={family}", "file"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return []

    paths: list[Path] = []
    seen: set[Path] = set()
    for line in result.stdout.splitlines():
        raw = line.split(":", 1)[0].strip()
        if not raw:
            continue
        path = Path(raw)
        if path.suffix.lower() not in {".ttf", ".otf"}:
            continue
        # Prefer the proportional UI face; skip Mono/Propo duplicates when
        # the requested family is the plain Nerd Font.
        name_l = path.name.lower()
        if "mono" in name_l or "propo" in name_l:
            if "mono" not in family.lower() and "propo" not in family.lower():
                continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        paths.append(resolved)
    return sorted(paths)


def _source_ttfs() -> tuple[list[Path], list[Path]]:
    """Return (source files to tune, reject_files for fontconfig)."""
    bundled = fonts_dir()
    if bundled.is_dir():
        files = sorted(bundled.glob("*.ttf"))
        return files, files

    system_files = _system_font_files(family_name())
    return system_files, system_files


def _prepare_family_ttfs() -> tuple[Path | None, list[Path]]:
    """Build tuned cache if needed. Returns (active_dir, reject_files)."""
    sources, reject_files = _source_ttfs()
    if not sources:
        return None, []

    if not _needs_transform():
        # Bundled unmodified: use assets dir. System unmodified: no cache.
        bundled = fonts_dir()
        if bundled.is_dir():
            return bundled, []
        return None, []

    dest_dir = _cache_family_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    y_scale = vertical_scale()
    track = tracking()

    for src in sources:
        dest = dest_dir / src.name
        if (
            not dest.exists()
            or dest.stat().st_mtime < src.stat().st_mtime
            or dest.stat().st_size == 0
        ):
            try:
                transform_font(src, dest, y_scale=y_scale, tracking=track)
            except Exception:
                logging.exception("Failed to transform font %s; copying source", src.name)
                shutil.copy2(src, dest)

    return dest_dir, reject_files


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
    family = family_name()
    active_dir, reject_files = _prepare_family_ttfs()

    if active_dir is None:
        logging.info("Using system font family %r as-is", family)
        if "CTkFont" in ThemeManager.theme:
            ThemeManager.theme["CTkFont"]["family"] = family
        _initialized = True
        return

    if sys.platform.startswith("linux"):
        refresh_fontconfig(
            active_family=family,
            active_dir=active_dir,
            reject_files=reject_files or None,
        )

    loaded_any = False
    for path in sorted(active_dir.glob("*.ttf")):
        if _install_font_file(path):
            loaded_any = True
        else:
            logging.warning("Failed to load font file: %s", path)

    if loaded_any and "CTkFont" in ThemeManager.theme:
        ThemeManager.theme["CTkFont"]["family"] = family
    elif "CTkFont" in ThemeManager.theme:
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
