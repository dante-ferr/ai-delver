"""Convert validated level sketches into full editor Level objects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from level.level import Level
from level.level_bootstrap._level_factory import LevelFactory
from level.sketch.borders import ensure_surrounding_walls
from level.sketch.schema import LevelSketch, LevelSketchError, parse_level_sketch
from level.world_object_sizes import world_object_size


DEFAULT_GOAL_TAGS = ["variation_battery_snack"]


class LevelSketchImporter:
    """Builds a full Level (with default visuals) from a dense sketch grid."""

    def __init__(self, factory: LevelFactory | None = None):
        self.factory = factory or LevelFactory()

    def import_sketch(self, data: LevelSketch | dict[str, Any]) -> Level:
        sketch = data if isinstance(data, LevelSketch) else parse_level_sketch(data)
        # Seal perimeter in the sketch grid first (authoring convenience).
        sketch = ensure_surrounding_walls(sketch)
        level = self.factory.create_blank_level((sketch.width, sketch.height))
        level.name = sketch.name

        essentials = level.map.world_objects_map.get_layer("essentials")
        tilemap = level.map.tilemap

        # 1) Platforms first — concurrent essentials would otherwise delete them.
        for y, row in enumerate(sketch.cells):
            for x, elements in enumerate(row):
                if "platform" in elements:
                    tilemap.create_basic_platform_at((x, y), apply_formatting=False)

        # 2) World objects (clear any concurrent platform across the footprint).
        for y, row in enumerate(sketch.cells):
            for x, elements in enumerate(row):
                position = (x, y)
                for element_id in elements:
                    if element_id == "delver":
                        essentials.create_world_object_at(
                            position,
                            "delver",
                            unique=True,
                            size=world_object_size("delver"),
                        )
                    elif element_id == "goal":
                        essentials.create_world_object_at(
                            position,
                            "goal",
                            tags=list(DEFAULT_GOAL_TAGS),
                            unique=True,
                            size=world_object_size("goal"),
                        )

        # 3) Re-seal perimeter after world objects (concurrency can punch holes).
        self._seal_perimeter_platforms(tilemap, sketch.width, sketch.height)

        tilemap.format_all_tiles()
        return level

    @staticmethod
    def _seal_perimeter_platforms(tilemap, width: int, height: int) -> None:
        platforms = tilemap.get_layer("platforms")
        for y in range(height):
            for x in range(width):
                if x == 0 or y == 0 or x == width - 1 or y == height - 1:
                    if platforms.get_tile_at((x, y)) is None:
                        tilemap.create_basic_platform_at(
                            (x, y), apply_formatting=False
                        )

    def import_file(self, path: str | Path) -> Level:
        path = Path(path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise LevelSketchError(f"Failed to read sketch file '{path}': {exc}") from exc

        import json

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LevelSketchError(f"Invalid JSON in sketch file '{path}': {exc}") from exc

        return self.import_sketch(data)
