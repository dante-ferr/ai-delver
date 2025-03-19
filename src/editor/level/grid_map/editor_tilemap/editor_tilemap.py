from pytiling import Tilemap
from typing import TYPE_CHECKING, cast, Literal
import os


if TYPE_CHECKING:
    from .editor_tilemap_layer import EditorTilemapLayer
    from pytiling import Tile, GridElement, GridLayer
    from editor.level.components.level_canvas import LevelCanvas
    from ..mixed_map import MixedMap


FLOOR_VARIATIONS_FILENAME = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "floor_variations.json"
)


class EditorTilemap(Tilemap):
    def __init__(
        self,
        mixed_map: "MixedMap",
        tile_size: tuple[int, int],
        grid_size: tuple[int, int] = (5, 5),
        min_grid_size: tuple[int, int] = (5, 5),
        max_grid_size: tuple[int, int] = (100, 100),
    ):
        super().__init__(tile_size, grid_size, min_grid_size, max_grid_size)
        self.mixed_map = mixed_map

        self._level_canvas: "LevelCanvas | None" = None

    def add_layer(self, layer: "GridLayer", position: int | Literal["end"] = "end"):
        """Add a layer to the tilemap."""
        super().add_layer(layer, position)

    def check_erase(self, element: "GridElement", layer_name: str):
        if layer_name == "walls":
            if element.name == "wall":
                self.create_basic_floor_at(element.position, apply_formatting=True)
        elif layer_name == "floor":
            if element.name == "floor":
                self.create_basic_wall_at(element.position, apply_formatting=True)

    def get_layer(self, name: str) -> "EditorTilemapLayer":
        """Get a layer by its name."""
        return cast("EditorTilemapLayer", super().get_layer(name))

    def create_basic_wall_at(self, position: tuple[int, int], **args):
        walls = self.get_layer("walls")
        tile = walls.create_autotile_tile_at(
            position,
            "wall",
            default_shallow_tile_variations=True,
            **args,
        )
        if tile is not None:
            self._reduce_grid_size_if_needed(tile)

        return tile

    def create_basic_floor_at(
        self, position: tuple[int, int], apply_formatting=False, **args
    ):
        floor = self.get_layer("floor")
        tile = floor.create_tile_at(position, (0, 0), "floor", **args)
        if tile is not None:
            tile.add_variations_from_json(
                FLOOR_VARIATIONS_FILENAME, apply_formatting=apply_formatting
            )

            self._expand_grid_size_if_needed(tile)

        return tile

    def _reduce_grid_size_if_needed(self, new_tile: "Tile"):
        tile_x, tile_y = new_tile.position
        walls = self.get_layer("walls")

        def _process_line(edge, walls=walls):
            full_of_walls = all(
                tile is not None and tile.name == "wall"
                for tile in walls.get_edge_tiles(edge, retreat=1)
            )

            if not full_of_walls:
                return
            deleted_elements = self.mixed_map.reduce_towards(edge)
            if not deleted_elements:
                return

            _process_line(edge)

        grid_width, grid_height = self.mixed_map.grid_size

        if tile_x == 1:
            _process_line("left")
        if tile_x == grid_width - 2:
            _process_line("right")
        if tile_y == 1:
            _process_line("top")
        if tile_y == grid_height - 2:
            _process_line("bottom")

    def _expand_grid_size_if_needed(self, new_tile: "Tile"):
        if new_tile.edges is None:
            return
        for edge in new_tile.edges:
            added_positions = self.mixed_map.expand_towards(edge)
            if not added_positions:
                continue
            for x, y in added_positions:
                self.create_basic_wall_at((x, y), apply_formatting=True)
