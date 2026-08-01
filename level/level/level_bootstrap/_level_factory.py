from pytiling import Tileset
from ..grid_map.editor_tilemap.editor_tilemap_layer import EditorTilemapLayer
from ..grid_map.world_objects_map import WorldObjectsLayer
from ..grid_map import MixedMap
from ..level import Level
from level.config import *
from level.world_object_sizes import world_object_size

MAP_SIZE = (START_MAP_WIDTH, START_MAP_HEIGHT)
TILE_SIZE = (TILE_WIDTH, TILE_HEIGHT)


def default_tilemap_layers() -> dict[str, EditorTilemapLayer]:
    """Tilemap layers every level must have, keyed by layer name."""
    return {
        "platforms": EditorTilemapLayer(
            "platforms",
            Tileset(str(ASSETS_PATH / "img/tilesets/dungeon/platforms.png")),
            str(ASSETS_PATH / "svg/wall.svg"),
        ),
        "traps": EditorTilemapLayer(
            "traps",
            Tileset(str(ASSETS_PATH / "img/tilesets/dungeon/spike_trap.png")),
            str(ASSETS_PATH / "svg/spike_trap.svg"),
        ),
    }


def ensure_configured_layers(mixed_map: MixedMap):
    """Add tilemap layers introduced after a level was saved (e.g. traps in old saves)."""
    missing = [
        layer_name
        for layer_name in TILEMAP_LAYER_NAMES
        if not mixed_map.tilemap.has_layer(layer_name)
    ]
    if not missing:
        return

    layers = default_tilemap_layers()
    for layer_name in missing:
        layer = layers[layer_name]
        mixed_map.tilemap.add_layer(layer)
        position = sum(
            1
            for existing in mixed_map.layers
            if LAYER_ORDER.index(existing.name) < LAYER_ORDER.index(layer_name)
        )
        mixed_map.add_layer(layer, position=position)

    if "traps" in missing and mixed_map.has_layer("essentials"):
        mixed_map.add_layer_concurrence("traps", "essentials")


class LevelFactory:

    def create_level(self):
        level = self.create_blank_level(MAP_SIZE)
        self._create_starting_tiles()
        self.tilemap.lock_edges_if_needed()
        self._create_starting_world_objects()
        return level

    def create_blank_level(self, grid_size: tuple[int, int]) -> Level:
        """Create an empty level shell (layers configured, no platforms or world objects)."""
        mixed_map = MixedMap(TILE_SIZE, grid_size, MIN_GRID_SIZE, MAX_GRID_SIZE)
        self.tilemap = mixed_map.tilemap
        self.world_objects_map = mixed_map.world_objects_map
        self._configure_tilemap()
        self._configure_world_objects_map()
        mixed_map.populate_layers()

        level = Level(mixed_map)
        level.map.add_layer_concurrence("platforms", "essentials")
        level.map.add_layer_concurrence("traps", "essentials")
        return level

    def _configure_tilemap(self):
        layers = default_tilemap_layers()

        for layer_name in LAYER_ORDER:
            if layer_name in TILEMAP_LAYER_NAMES:
                self.tilemap.add_layer(layers[layer_name])

    def _create_starting_tiles(self):
        for position in self.tilemap.get_edge_positions():
            self.tilemap.create_basic_platform_at(position, apply_formatting=False)

        self.tilemap.format_all_tiles()

    def _configure_world_objects_map(self):
        essentials = WorldObjectsLayer(
            "essentials", str(ASSETS_PATH / "svg/important.svg")
        )
        self.world_objects_map.add_layer(essentials)

    def _create_starting_world_objects(self):
        essentials_layer = self.world_objects_map.get_layer("essentials")

        essentials_layer.create_world_object_at(
            START_DELVER_POSITION,
            "delver",
            unique=True,
            size=world_object_size("delver"),
        )
        essentials_layer.create_world_object_at(
            START_GOAL_POSITION,
            "goal",
            tags=["variation_battery_snack"],
            unique=True,
            size=world_object_size("goal"),
        )
