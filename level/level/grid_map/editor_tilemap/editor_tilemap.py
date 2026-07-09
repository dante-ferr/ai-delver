from pytiling import Tilemap, opposite_directions
from typing import TYPE_CHECKING, cast, Literal
import os


if TYPE_CHECKING:
    from .editor_tilemap_layer import EditorTilemapLayer
    from pytiling import (
        Tile,
        GridLayer,
        AutotileTile,
        Direction,
    )
    from ..mixed_map import MixedMap


class EditorTilemap(Tilemap):
    SHALLOW_PLATFORMS_VARIATIONS = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "shallow_platforms_variations.json"
    )

    def __init__(
        self,
        tile_size: tuple[int, int],
        grid_size: tuple[int, int] = (5, 5),
        min_grid_size: tuple[int, int] = (5, 5),
        max_grid_size: tuple[int, int] = (100, 100),
        mixed_map: "MixedMap | None" = None,
    ):
        """
        Initialize the EditorTilemap with optional mixed_map reference.
        If mixed_map is not provided right away, it can must be set later to allow
        acessing the MixedMap methods like 'reduce_towards' and 'expand_towards'.
        """
        super().__init__(tile_size, grid_size, min_grid_size, max_grid_size)
        self.locked_edges = set()
        self._mixed_map = mixed_map

    def to_dict(self):
        """Serialize the tilemap to a dictionary."""
        data = super().to_dict()
        data["__class__"] = "EditorTilemap"
        return data

    @classmethod
    def from_dict(cls, data: dict):
        """
        Deserialize a tilemap from a dictionary.
        Note: This does not handle layer concurrences. The parent MixedMap is responsible for that.
        """
        return cls._from_dict_base(data)

    def add_layer(self, layer: "GridLayer", position: int | Literal["end"] = "end"):
        """Add a layer to the tilemap."""
        super().add_layer(layer, position)

    def get_layer(self, name: str) -> "EditorTilemapLayer":
        """Get a layer by its name."""
        return cast("EditorTilemapLayer", super().get_layer(name))

    def create_basic_platform_at(
        self, position: tuple[int, int], dynamic_resizing=False, **args
    ):
        platforms = self.get_layer("platforms")
        tile = platforms.create_autotile_tile_at(
            position,
            "platform",
            **args,
        )
        if tile is not None:

            def _callback(sender, tile: "AutotileTile"):
                if tile.is_shallow:
                    tile.add_variations_from_json(self.SHALLOW_PLATFORMS_VARIATIONS)

            tile.events["post_autotile"].connect(_callback, weak=False)

            if dynamic_resizing:
                self._dynamic_reduce_grid(tile)

        return tile

    def create_multiple_platforms_at(self, positions: list[tuple[int, int]]):
        tiles: list["AutotileTile"] = []
        for x, y in positions:
            tile = self.create_basic_platform_at((x, y), apply_formatting=False)
            if tile:
                tiles.append(tile)
            else:
                # A reason for a tile not to be added here is that there is already one in place.
                # In that case, we format the existing tile for it to respond to the new surroundings.
                tile_in_place = self.get_layer("platforms").get_tile_at((x, y))
                if tile_in_place:
                    tile_in_place.format()

        for tile in tiles:
            tile.format()

    def remove_platform_at(
        self, position: tuple[int, int], dynamic_resizing=False, apply_formatting=False
    ):
        platforms = self.get_layer("platforms")
        removed_tile = platforms.remove_tile_at(position, apply_formatting)
        if removed_tile is not None and dynamic_resizing:
            self._dynamic_expand_grid(removed_tile)

        return removed_tile

    def _dynamic_reduce_grid(self, new_tile: "Tile"):
        if self._is_semiedge(new_tile.position) is False:
            return

        grid_width, grid_height = self.mixed_map.grid_size
        tile_x, tile_y = new_tile.position

        if tile_x == 1:
            self.reduce_towards_if_needed("left")
        if tile_x == grid_width - 2:
            self.reduce_towards_if_needed("right")
        if tile_y == 1:
            self.reduce_towards_if_needed("top")
        if tile_y == grid_height - 2:
            self.reduce_towards_if_needed("bottom")

    def reduce_towards_if_needed(self, edge, first=True):
        platforms = self.get_layer("platforms")

        full_of_platforms = all(
            tile is not None and tile.name == "platform"
            for tile in platforms.get_edge_tiles(edge, retreat=1)
        )

        if not full_of_platforms:
            return
        deleted_elements = self.mixed_map.reduce_towards(edge)

        # Unlock the edge and its opposite if this was the first reduction, to allow further expansions
        if first:
            self.unlock_edge(edge)
            self.unlock_edge(opposite_directions[edge])

        if not deleted_elements:
            return

        self.reduce_towards_if_needed(edge, first=False)

    def reduce_if_needed(self):
        for edge in ["left", "right", "top", "bottom"]:
            self.reduce_towards_if_needed(edge)

    def _dynamic_expand_grid(self, new_tile: "Tile"):
        if new_tile.edges is None:
            return
        for edge in new_tile.edges:
            self.mixed_map.expand_towards(edge)
            self.lock_edge_axis_if_needed(edge)

    def lock_edge(self, edge: "Direction"):
        self.locked_edges.add(edge)

        platforms = self.get_layer("platforms")
        elements = platforms.get_edge_elements(edge)
        for element in elements:
            if element is not None:
                element.locked = True

    def lock_edges_if_needed(self):
        self.lock_edge_axis_if_needed("left")
        self.lock_edge_axis_if_needed("top")

    def lock_edge_axis_if_needed(self, edge: "Direction"):
        if (edge == "left" or edge == "right") and self.grid_size[
            0
        ] == self.max_grid_size[0]:
            self.lock_edge("left")
            self.lock_edge("right")

        elif (edge == "top" or edge == "bottom") and self.grid_size[
            1
        ] == self.max_grid_size[1]:
            self.lock_edge("top")
            self.lock_edge("bottom")

    def lock_all_edges(self):
        for edge in ["left", "right", "top", "bottom"]:
            edge = cast("Direction", edge)
            self.lock_edge(edge)

    def unlock_edge(self, edge: "Direction"):
        self.locked_edges.discard(edge)

        platforms = self.get_layer("platforms")
        elements = platforms.get_edge_elements(edge)
        for element in elements:
            if element is not None:
                element.locked = False

    def unlock_expandable_edges(self):
        for edge in ["left", "right", "top", "bottom"]:
            edge = cast("Direction", edge)
            self.unlock_edge_if_expandable(edge)

    def unlock_edge_if_expandable(self, edge: "Direction"):
        if (edge == "left" or edge == "right") and self.grid_size[
            0
        ] < self.max_grid_size[0]:
            self.unlock_edge(edge)
        elif (edge == "top" or edge == "bottom") and self.grid_size[
            1
        ] < self.max_grid_size[1]:
            self.unlock_edge(edge)

    def _is_semiedge(self, position: tuple[int, int]) -> bool:
        x, y = position
        grid_width, grid_height = self.grid_size

        return x == 1 or x == grid_width - 2 or y == 1 or y == grid_height - 2

    @property
    def mixed_map(self):
        if self._mixed_map is None:
            raise ValueError("MixedMap reference is not set.")
        return self._mixed_map

    @mixed_map.setter
    def mixed_map(self, value: "MixedMap | None"):
        """
        Set the mixed_map reference.
        This is useful if the mixed_map is not available during initialization.
        """
        self._mixed_map = value
