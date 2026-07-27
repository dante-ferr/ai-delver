"""Register bundled ``assets/fonts/*`` with fontconfig before Tk starts (Linux).

Must run from bootstrap before ``customtkinter`` / Tk is imported.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    # this file: client/src/bundled_fonts.py → repo root
    return Path(__file__).resolve().parent.parent.parent


def fonts_conf_path() -> Path:
    conf_dir = Path(__file__).resolve().parent.parent / "data"
    conf_dir.mkdir(parents=True, exist_ok=True)
    return conf_dir / "fonts.conf"


def fonts_cache_root() -> Path:
    root = Path(__file__).resolve().parent.parent / "data" / "fonts_cache"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_conf(
    dirs: list[Path],
    *,
    reject_files: list[Path] | None = None,
) -> Path | None:
    if not sys.platform.startswith("linux"):
        return None
    if not dirs:
        return None

    conf_path = fonts_conf_path()
    dir_xml = "\n".join(f"  <dir>{d.resolve()}</dir>" for d in dirs)
    reject_xml = ""
    if reject_files:
        patterns = []
        for path in reject_files:
            resolved = path.resolve()
            patterns.append(
                "    <pattern>\n"
                f'      <patelt name="file"><string>{resolved}</string></patelt>\n'
                "    </pattern>"
            )
        reject_xml = (
            "\n  <selectfont>\n"
            "    <rejectfont>\n"
            + "\n".join(patterns)
            + "\n    </rejectfont>\n"
            "  </selectfont>\n"
        )
    conf_path.write_text(
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">\n'
        "<fontconfig>\n"
        '  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>\n'
        f"{dir_xml}\n"
        f"{reject_xml}"
        "</fontconfig>\n",
        encoding="utf-8",
    )
    os.environ["FONTCONFIG_FILE"] = str(conf_path.resolve())
    return conf_path


def prepare_fontconfig() -> None:
    if os.environ.get("FONTCONFIG_FILE"):
        return
    fonts_root = _repo_root() / "assets" / "fonts"
    if not fonts_root.is_dir():
        return
    family_dirs = sorted(p for p in fonts_root.iterdir() if p.is_dir())
    _write_conf(family_dirs)


def refresh_fontconfig(
    *,
    active_family: str,
    active_dir: Path,
    reject_files: list[Path] | None = None,
) -> None:
    """Point the active family at ``active_dir`` (tuned cache), keep other bundles."""
    fonts_root = _repo_root() / "assets" / "fonts"
    dirs: list[Path] = [active_dir]
    if fonts_root.is_dir():
        for p in sorted(fonts_root.iterdir()):
            if p.is_dir() and p.name != active_family:
                dirs.append(p)
    conf = _write_conf(dirs, reject_files=reject_files)
    if conf is None:
        return
    subprocess.run(
        ["fc-cache", "-f", str(active_dir.resolve())],
        check=False,
        capture_output=True,
    )
