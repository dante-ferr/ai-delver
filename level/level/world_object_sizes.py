"""Default grid footprints for world objects (bottom-left anchored, size in tiles)."""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

from level.config import TILE_HEIGHT, TILE_WIDTH


# Explicit overrides / non-physics objects. Delver is derived from delver.toml.
_STATIC_SIZES: dict[str, tuple[int, int]] = {
    "goal": (2, 2),
}


def default_delver_toml() -> Path:
    from level.config import PROJECT_ROOT

    return PROJECT_ROOT / "runtime" / "src" / "world_objects" / "delver" / "delver.toml"


@lru_cache(maxsize=4)
def delver_size_tiles(
    delver_toml: str | None = None,
    tile_width: int = TILE_WIDTH,
    tile_height: int = TILE_HEIGHT,
) -> tuple[int, int]:
    """Ceil of physics AABB in tiles so the footprint covers the standing body."""
    try:
        import tomllib
    except ModuleNotFoundError:  # Python < 3.11
        import tomli as tomllib  # type: ignore

    path = Path(delver_toml) if delver_toml else default_delver_toml()
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    width_px = float(data["player_width"])
    height_px = float(data["player_height"])
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
