from typing import Any, TYPE_CHECKING

from .world_objects import WorldObjectsController
from .world_objects.delver import Delver
from .world_objects.goal import Goal
from . import runtime_core

if TYPE_CHECKING:
    from level.level import Level


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
        goal_tiles = []
        delver_start = None
        for element in essentials.elements:
            if element.name == "goal":
                goal_tiles.append((element.position[0], element.position[1]))
            elif element.name == "delver":
                delver_start = element.position

        actual_pos = level.map.grid_pos_to_actual_pos(delver_start)
        start_x = actual_pos[0] + level.map.tile_size[0] / 2
        start_y = actual_pos[1] + level.map.tile_size[1] / 2

        self.physics_engine = runtime_core.RustPhysicsEngine(
            width,
            height,
            solid_tiles,
            goal_tiles,
            start_x,
            start_y,
            level.map.tile_size[0],
        )

        self.world_objects_controller = WorldObjectsController()
        self.delver = Delver(self, render=render)
        self.goal = Goal(self, variation="default", render=render)

        self.world_objects_controller.add_world_object(self.delver, unique_identifier="delver")
        self.world_objects_controller.add_world_object(self.goal, unique_identifier="goal")

    def update(self, dt: float):
        self.world_objects_controller.update_world_objects(dt)
        if self.physics:
            self.physics_engine.step(dt, self.delver.pending_run, self.delver.pending_jump)
            self.delver.pending_run = 0.0
            self.delver.pending_jump = False

    def run(self):
        self.running = True

    def stop(self):
        self.running = False

    @property
    def tilemap(self):
        return self.level.map.tilemap
