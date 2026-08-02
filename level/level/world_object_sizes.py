"""Default grid footprints for world objects (bottom-left anchored, size in tiles)."""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

from level.config import config as level_config


# Explicit overrides / non-physics objects. Delver is derived from delver.toml.
_STATIC_SIZES: dict[str, tuple[int, int]] = {
    "goal": (2, 2),
}


def default_delver_toml() -> Path:
    return (
        level_config.PROJECT_ROOT
        / "runtime"
        / "src"
        / "world_objects"
        / "delver"
        / "delver.toml"
    )


def delver_size_tiles(
    delver_toml: str | None = None,
    tile_width: int | None = None,
    tile_height: int | None = None,
) -> tuple[int, int]:
    """Ceil of physics AABB in tiles so the footprint covers the standing body."""
    tw = int(tile_width if tile_width is not None else level_config.TILE_WIDTH)
    th = int(tile_height if tile_height is not None else level_config.TILE_HEIGHT)
    path = str(delver_toml) if delver_toml else str(default_delver_toml())
    return _delver_size_tiles_cached(path, tw, th)


@lru_cache(maxsize=8)
def _delver_size_tiles_cached(
    delver_toml: str,
    tile_width: int,
    tile_height: int,
) -> tuple[int, int]:
    try:
        import tomllib
    except ModuleNotFoundError:  # Python < 3.11
        import tomli as tomllib  # type: ignore

    with Path(delver_toml).open("rb") as handle:
        data = tomllib.load(handle)
    width_px = float(data["physics_width"])
    height_px = float(data["physics_height"])
    return (
        max(1, math.ceil(width_px / tile_width)),
        max(1, math.ceil(height_px / tile_height)),
    )


def world_object_size(name: str) -> tuple[int, int]:
    """Return the default tile footprint for a world-object name."""
    if name in _STATIC_SIZES:
        return _STATIC_SIZES[name]
    if name == "delver":
        return delver_size_tiles()
    return (1, 1)
