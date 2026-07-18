from typing import Any, TYPE_CHECKING

from pytiling import footprint_positions

from .world_objects import WorldObjectsController
from .world_objects.delver import Delver
from .world_objects.goal import Goal
from . import runtime_core

if TYPE_CHECKING:
    from level.level import Level


def _delver_player_height_px() -> float:
    try:
        import tomllib
    except ModuleNotFoundError:  # Python < 3.11
        import tomli as tomllib  # type: ignore

    from level.world_object_sizes import default_delver_toml

    with default_delver_toml().open("rb") as handle:
        return float(tomllib.load(handle)["player_height"])


def _element_footprint_size(element) -> tuple[int, int]:
    """Prefer persisted size; fall back to the registry for legacy 1x1 saves."""
    from level.world_object_sizes import world_object_size

    size = getattr(element, "size", (1, 1))
    size = (int(size[0]), int(size[1]))
    if size == (1, 1):
        return world_object_size(element.name)
    return size


class Runtime:
    def __init__(self, level: Any, render: bool, physics: bool = True):
        self.render = render
        self.level: "Level" = level
        self.physics = physics
        self.running = False
        self.is_replay = False

        platforms_layer = level.map.tilemap.get_layer("platforms")
        height, width = platforms_layer.grid.shape
        solid_tiles = [
            (x, y)
            for y in range(height)
            for x in range(width)
            if platforms_layer.grid[y, x] is not None
        ]

        essentials = level.map.world_objects_map.get_layer("essentials")
        goal_tiles: list[tuple[int, int]] = []
        delver_element = None
        for element in essentials.elements:
            if element.name == "goal":
                goal_tiles.extend(
                    footprint_positions(
                        element.position, _element_footprint_size(element)
                    )
                )
            elif element.name == "delver":
                delver_element = element

        if delver_element is None:
            raise ValueError("Level is missing a delver world object.")

        tile_w, tile_h = level.map.tile_size
        player_height = _delver_player_height_px()
        bx, by = delver_element.position
        size_w = _element_footprint_size(delver_element)[0]
        # Match Rust Level::delver_spawn_center (Rapier Y-up).
        start_x = (bx + size_w * 0.5) * tile_w
        cell_bottom = (height - by - 1) * tile_h
        start_y = cell_bottom + player_height / 2.0

        self.physics_engine = runtime_core.RustPhysicsEngine(
            width,
            height,
            solid_tiles,
            goal_tiles,
            start_x,
            start_y,
            tile_w,
        )

        self.world_objects_controller = WorldObjectsController()
        self.delver = Delver(self, render=render)
        self.goal = Goal(self, render=render)

        self.world_objects_controller.add_world_object(self.delver, unique_identifier="delver")
        self.world_objects_controller.add_world_object(self.goal, unique_identifier="goal")

    def update(self, dt: float):
        self.world_objects_controller.update_world_objects(dt)
        if self.physics:
            self.physics_engine.step(dt)

    def run(self):
        self.running = True

    def stop(self):
        self.running = False

    @property
    def tilemap(self):
        return self.level.map.tilemap
