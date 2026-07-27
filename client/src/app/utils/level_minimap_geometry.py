"""Parse level JSON into geometry consumed by Minimap / TrajectoryMinimap."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LevelMinimapGeometry:
    grid_size: tuple[int, int]
    tile_size: tuple[int, int]
    walls: list[tuple[int, int]]
    start_pos: tuple[int, int] | None
    goal_pos: tuple[int, int] | None


def parse_level_minimap_geometry(level_data: dict[str, Any]) -> LevelMinimapGeometry:
    """Extract grid size, walls (platforms), and start/goal from level JSON."""
    map_data = level_data.get("map", {}) or {}
    raw_grid = map_data.get("grid_size", [27, 27])
    raw_tile = map_data.get("tile_size", [16, 16])
    grid_size = (int(raw_grid[0]), int(raw_grid[1]))
    tile_size = (int(raw_tile[0]), int(raw_tile[1]))

    walls: list[tuple[int, int]] = []
    tilemap = map_data.get("tilemap", {}) or {}
    for layer in tilemap.get("layers", []) or []:
        if layer.get("name") == "platforms":
            for elem in layer.get("elements", []) or []:
                if elem.get("name") == "platform":
                    pos = elem.get("position")
                    if pos:
                        walls.append((int(pos[0]), int(pos[1])))

    start_pos = None
    goal_pos = None
    world_objects_map = map_data.get("world_objects_map", {}) or {}
    for layer in world_objects_map.get("layers", []) or []:
        if layer.get("name") == "essentials":
            for elem in layer.get("elements", []) or []:
                name = elem.get("name")
                pos = elem.get("position")
                if not pos:
                    continue
                point = (int(pos[0]), int(pos[1]))
                if name == "delver":
                    start_pos = point
                elif name == "goal":
                    goal_pos = point

    return LevelMinimapGeometry(
        grid_size=grid_size,
        tile_size=tile_size,
        walls=walls,
        start_pos=start_pos,
        goal_pos=goal_pos,
    )
