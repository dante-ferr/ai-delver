from pytiling import GridMap
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from .world_objects_layer import WorldObjectsLayer
    from .world_object import WorldObjectRepresentation
    from ..mixed_map import MixedMap


class WorldObjectsMap(GridMap):

    def __init__(
        self,
        tile_size: tuple[int, int],
        grid_size: tuple[int, int] = (5, 5),
        min_grid_size: tuple[int, int] = (5, 5),
        max_grid_size: tuple[int, int] = (100, 100),
        mixed_map: "MixedMap | None" = None,
    ):
        super().__init__(tile_size, grid_size, min_grid_size, max_grid_size)
        self.mixed_map = mixed_map

    def to_dict(self):
        """Serialize the map to a dictionary."""
        data = super().to_dict()
        data["__class__"] = "WorldObjectsMap"
        return data

    @classmethod
    def from_dict(cls, data: dict):
        """
        Deserialize a map from a dictionary.
        Note: This does not handle layer concurrences. The parent MixedMap is responsible for that.
        """
        return cls._from_dict_base(data)

    def get_layer(self, name: str):
        """Get a layer by its name."""
        return cast("WorldObjectsLayer", super().get_layer(name))

    @property
    def all_world_objects(self):
        return cast(list["WorldObjectRepresentation"], self.all_elements)

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
