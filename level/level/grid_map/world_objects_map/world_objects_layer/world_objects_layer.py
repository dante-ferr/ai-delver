from pytiling import GridLayer
from ..world_object import WorldObjectRepresentation


class WorldObjectsLayer(GridLayer):
    def __init__(self, name: str, icon_path: str):
        super().__init__(name)
        self.icon_path = icon_path

    def to_dict(self):
        """Serialize the layer to a dictionary with asset-relative paths."""
        from level.utils import to_asset_relative_path

        data = super().to_dict()
        data["__class__"] = "WorldObjectsLayer"
        data["icon_path"] = to_asset_relative_path(self.icon_path)
        return data

    def create_world_object_at(self, position: tuple[int, int], name: str, **args):
        world_object = WorldObjectRepresentation(position, name, **args)
        self.add_element(world_object)
        return world_object
