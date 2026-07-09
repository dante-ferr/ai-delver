from pytiling import GridMap
from typing import TYPE_CHECKING, cast
from .editor_tilemap import EditorTilemap
from .world_objects_map import WorldObjectsMap
from level.config import LAYER_ORDER

if TYPE_CHECKING:
    from level.grid_map.editor_tilemap.editor_tilemap_layer import (
        EditorTilemapLayer,
    )
    from level.grid_map.world_objects_map.world_objects_layer.world_objects_layer import (
        WorldObjectsLayer,
    )
    from pytiling import AutotileTile, Direction


class MixedMap(GridMap):
    def __init__(
        self,
        tile_size: tuple[int, int],
        grid_size: tuple[int, int],
        min_grid_size: tuple[int, int],
        max_grid_size: tuple[int, int],
    ):
        super().__init__(tile_size, grid_size, min_grid_size, max_grid_size)

        self.tilemap = EditorTilemap(
            tile_size, grid_size, min_grid_size, max_grid_size, mixed_map=self
        )
        self.world_objects_map = WorldObjectsMap(
            tile_size, grid_size, min_grid_size, max_grid_size, mixed_map=self
        )

    def to_dict(self):
        """Serialize the map to a dictionary."""
        return {
            "__class__": "MixedMap",
            "tile_size": self.tile_size,
            "grid_size": self.grid_size,
            "min_grid_size": self.min_grid_size,
            "max_grid_size": self.max_grid_size,
            "tilemap": self.tilemap.to_dict(),
            "world_objects_map": self.world_objects_map.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Deserialize a map from a dictionary."""
        instance = cls._instance_from_data(data)

        instance.tilemap = EditorTilemap.from_dict(data["tilemap"])
        instance.tilemap.mixed_map = instance
        instance.world_objects_map = WorldObjectsMap.from_dict(
            data["world_objects_map"]
        )
        instance.world_objects_map.mixed_map = instance

        instance.populate_layers()

        # After all layers are loaded into the sub-maps and populated into the
        # main map, establish the concurrences.
        all_layers_data = (
            data["tilemap"]["layers"] + data["world_objects_map"]["layers"]
        )

        cls._setup_concurrency_from_data(all_layers_data, instance)

        return instance

    def populate_layers(self):
        for layer_name in LAYER_ORDER:
            if self.tilemap.has_layer(layer_name):
                self.add_layer(self.tilemap.get_layer(layer_name))

            if self.world_objects_map.has_layer(layer_name):
                self.add_layer(self.world_objects_map.get_layer(layer_name))

    def get_tilemap_layer(self, name: str):
        """Get a tilemap layer. Use this function if you want the tilemap layer type assigned to a variable."""
        return self.tilemap.get_layer(name)

    def get_world_objects_layer(self, name: str):
        """Get a world objects layer. Use this function if you want the world objects layer type assigned to a variable."""
        return self.world_objects_map.get_layer(name)

    def get_layer(self, name: str):
        """Get a layer by its name."""
        return cast("WorldObjectsLayer | EditorTilemapLayer", super().get_layer(name))

    @property
    def layers(self):
        """Returns a list of layers in the correct order."""
        return cast(list["WorldObjectsLayer | EditorTilemapLayer"], super().layers)

    @property
    def grid_size(self):
        return self.tilemap.grid_size

    @grid_size.setter
    def grid_size(self, value: tuple[int, int]):
        self.tilemap.grid_size = value
        self.world_objects_map.grid_size = value
        self._grid_size = self.clamp_size(value)

    def expand_towards(self, direction, size=1, dynamic_resizing=False):
        # Unlock the previously locked edge if the map can be expanded in that direction.
        # It's done while dynamic resizing is disabled because in this scenario the edges
        # should be locked.

        if not dynamic_resizing:
            self.tilemap.unlock_edge_if_expandable(direction)

        new_positions = super().expand_towards(direction, size)

        if not new_positions:
            return new_positions

        self.tilemap.create_multiple_platforms_at(new_positions)

        # Locking the edge again.
        if not dynamic_resizing:
            self.tilemap.lock_all_edges()

        return new_positions

    def multidirectional_expand_towards(self, directions: "list[Direction]", size: int):
        """Expands the map in multiple directions, distributing size per axis and prioritizing remainders."""
        h_dirs = [d for d in directions if d in ("left", "right")]
        v_dirs = [d for d in directions if d in ("top", "bottom")]

        if h_dirs:
            available_h = self.max_grid_size[0] - self.grid_size[0]
            total_h_expand = min(available_h, len(h_dirs) * size)

            h_size = total_h_expand // len(h_dirs)
            h_rem = total_h_expand % len(h_dirs)

            # Sort to process left before right, ensuring right gets the remainder
            for direction in sorted(h_dirs):
                expand_size = h_size
                if h_rem > 0 and direction == "right":
                    expand_size += h_rem
                if expand_size > 0:
                    self.expand_towards(direction, expand_size)

        if v_dirs:
            available_v = self.max_grid_size[1] - self.grid_size[1]
            total_v_expand = min(available_v, len(v_dirs) * size)

            v_size = total_v_expand // len(v_dirs)
            v_rem = total_v_expand % len(v_dirs)

            # Sort to process top before bottom, ensuring bottom gets the remainder
            for direction in sorted(v_dirs, reverse=True):
                expand_size = v_size
                if v_rem > 0 and direction == "bottom":
                    expand_size += v_rem
                if expand_size > 0:
                    self.expand_towards(direction, expand_size)

    def _get_clamped_expansion_size(self, direction, size):
        if direction in ("right", "left"):
            clamped_size = min(size, self.max_grid_size[0] - self.grid_size[0])
        else:
            clamped_size = min(size, self.max_grid_size[1] - self.grid_size[1])
        return clamped_size

    def reduce_towards(self, direction, size=1):
        deleted_elements = super().reduce_towards(direction, size)

        self.tilemap.create_multiple_platforms_at(self.get_edge_positions(direction, 1))
        self.tilemap.lock_edge(direction)

        return deleted_elements

    def multidirectional_reduce_towards(self, directions: "list[Direction]", size: int):
        """Reduces the map from multiple directions, distributing size per axis and prioritizing remainders."""
        h_dirs: "list[Direction]" = [d for d in directions if d in ("left", "right")]
        v_dirs: "list[Direction]" = [d for d in directions if d in ("top", "bottom")]
        abs_size = abs(size)

        if h_dirs:
            available_h = self.grid_size[0] - self.min_grid_size[0]
            total_h_reduce = min(available_h, len(h_dirs) * abs_size)

            h_size = total_h_reduce // len(h_dirs)
            h_rem = total_h_reduce % len(h_dirs)

            # Sort to process left before right, ensuring right gets the remainder
            for direction in sorted(h_dirs):
                reduce_size = h_size
                if h_rem > 0 and direction == "right":
                    reduce_size += h_rem
                if reduce_size > 0:
                    self.reduce_towards(direction, reduce_size)

        if v_dirs:
            available_v = self.grid_size[1] - self.min_grid_size[1]
            total_v_reduce = min(available_v, len(v_dirs) * abs_size)

            v_size = total_v_reduce // len(v_dirs)
            v_rem = total_v_reduce % len(v_dirs)

            # Sort to process top before bottom, ensuring bottom gets the remainder
            for direction in sorted(v_dirs, reverse=True):
                reduce_size = v_size
                if v_rem > 0 and direction == "bottom":
                    reduce_size += v_rem
                if reduce_size > 0:
                    self.reduce_towards(direction, reduce_size)

    def _get_clamped_reduction_size(self, direction, size):
        if direction in ("right", "left"):
            clamped_size = min(size, self.grid_size[0] - self.min_grid_size[0])
        else:
            clamped_size = min(size, self.grid_size[1] - self.min_grid_size[1])

        return clamped_size
