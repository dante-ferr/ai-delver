"""Ensure pyglet_dragonbones exporters are importable."""

from __future__ import annotations

import sys

from src.config import config


def ensure_dragonbones_on_path() -> None:
    lib_path = config.PROJECT_ROOT / "pyglet-dragonbones-lib"
    lib_str = str(lib_path)
    if lib_str not in sys.path:
        sys.path.insert(0, lib_str)
