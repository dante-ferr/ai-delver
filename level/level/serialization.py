from pytiling.serialization import (
    register_element_deserializer,
    register_layer_deserializer,
    register_map_deserializer,
)
from pytiling.tileset import Tileset
from level.utils import from_asset_relative_path


def initialize_level_deserializers():
    """Registers the deserializers for the level-specific classes."""

    def _deserialize_world_object_representation(data):
        from .grid_map.world_objects_map.world_object import (
            WorldObjectRepresentation,
        )

        return WorldObjectRepresentation.from_dict(data)

    def _deserialize_editor_tilemap_layer(data, tilesets: dict[str, "Tileset"]):
        from .grid_map.editor_tilemap.editor_tilemap_layer import (
            EditorTilemapLayer,
        )

        # The key for the cache should be the relative path from the file
        relative_tileset_path = data["tileset"]
        if relative_tileset_path not in tilesets:
            absolute_tileset_path = from_asset_relative_path(relative_tileset_path)
            tilesets[relative_tileset_path] = Tileset(str(absolute_tileset_path))
        tileset = tilesets[relative_tileset_path]

        absolute_icon_path = from_asset_relative_path(data["icon_path"])

        return EditorTilemapLayer(
            name=data["name"], tileset=tileset, icon_path=str(absolute_icon_path)
        )

    def _deserialize_world_objects_layer(data, tilesets: dict[str, "Tileset"]):
        from .grid_map.world_objects_map.world_objects_layer import (
            WorldObjectsLayer,
        )

        absolute_icon_path = from_asset_relative_path(data["icon_path"])

        return WorldObjectsLayer(name=data["name"], icon_path=str(absolute_icon_path))

    def _deserialize_mixed_map(data):
        from .grid_map import MixedMap

        return MixedMap.from_dict(data)

    register_element_deserializer(
        "WorldObjectRepresentation", _deserialize_world_object_representation
    )
    register_layer_deserializer("EditorTilemapLayer", _deserialize_editor_tilemap_layer)
    register_layer_deserializer("WorldObjectsLayer", _deserialize_world_objects_layer)
    register_map_deserializer("MixedMap", _deserialize_mixed_map)
