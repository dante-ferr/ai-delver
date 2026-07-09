from typing import cast, Any
from .world_objects import WorldObjectsController, WorldObject
from .world_objects.entities.delver import Delver
from .world_objects.items import Goal
import pymunk
from pytiling import (
    TilemapBorderTracer,
    PymunkTilemapPhysics,
)
from typing import TYPE_CHECKING
from .config import PHYSICS_FPS, GRAVITY

if TYPE_CHECKING:
    from level.level import Level


class Runtime:

    def __init__(self, level: Any, render: bool, physics: bool = True):
        self.render = render
        self.level: "Level" = level
        self.space = pymunk.Space()
        self.space.gravity = (0, GRAVITY)

        # FIX 1: Increase Collision Slop
        # 0.01 is too strict and causes instability/sinking due to floating point noise.
        # 0.1 is standard, but for tilemaps 0.5 often feels smoother.
        self.space.collision_slop = 0.1

        # FIX 2: Tune Collision Bias (Stiffness)
        # Your previous value (0.15) only corrected 15% of overlap per step, causing sinking.
        # We increase this to 0.9 (90%) to make the ground feel solid and snappy.
        # Pymunk formula: bias = 1.0 - remaining_overlap_percent ** (1/dt)
        # We want to remove 90% of overlap per step.
        correction_percentage = 0.9
        self.space.collision_bias = pow(1.0 - correction_percentage, PHYSICS_FPS)

        # High iterations are good for stability, 60 is excellent.
        self.space.iterations = 60

        self.execution_speed = 1.0

        self.physics = physics
        self.physics_dt = 1.0 / PHYSICS_FPS
        self.physics_accumulator = 0.0

        self._setup_platform_physics()

        self.running = False
        self.is_replay = False

        self.world_objects_controller = self.world_objects_controller_factory(
            self.space
        )
        self.delver = cast(
            "Delver", self.world_objects_controller.get_world_object("delver")
        )
        self.goal = self.world_objects_controller.get_world_object("goal")

    def update(self, dt):
        # We update the logic/AI of world objects.
        # Note: We should ideally NOT apply physics forces here directly,
        # but rather set "intent" that is applied in the physics step.
        self.world_objects_controller.update_world_objects(dt)

        if self.physics:
            self.update_physics(dt)

    def update_physics(self, dt):
        self.physics_accumulator += dt

        # We cap the accumulator to prevent the "spiral of death"
        # if the game lags significantly (e.g. breakpoint or heavy load).
        if self.physics_accumulator > 0.25:
            self.physics_accumulator = 0.25

        while self.physics_accumulator >= self.physics_dt:
            # Pymunk clears forces after every step. If we step twice in one frame
            # (to catch up), the second step would have ZERO move force if we didn't
            # re-apply it here.
            self._apply_continuous_forces()

            self.space.step(self.physics_dt)
            self.physics_accumulator -= self.physics_dt

    def _apply_continuous_forces(self):
        """
        Re-applies forces that should persist across physics steps.
        This is necessary because space.step() clears all forces on bodies.
        """
        # For now it should be empty. I might add stuff here if it's needed.
        pass

    def run(self):
        self.running = True

    def stop(self):
        if not self.running:
            return
        self.running = False

    @property
    def tilemap(self):
        return self.level.map.tilemap

    def _setup_platform_physics(self):
        platforms = self.level.map.tilemap.get_layer("platforms")
        border_tracer = TilemapBorderTracer(platforms)
        PymunkTilemapPhysics(border_tracer, self.space)

    def world_objects_controller_factory(self, space: "pymunk.Space"):
        world_objects_controller = WorldObjectsController()

        def _place_world_object(world_object: "WorldObject", **args):
            world_object_actual_pos = self.level.map.grid_pos_to_actual_pos(
                element.position
            )
            world_object.position = (
                world_object_actual_pos[0] + self.level.map.tile_size[0] / 2,
                world_object_actual_pos[1] + self.level.map.tile_size[1] / 2,
            )
            world_objects_controller.add_world_object(world_object, **args)

        def _delver_factory(element):
            delver = Delver(self, space=space, render=self.render)
            _place_world_object(delver, unique_identifier="delver")

        def _goal_factory(element):
            goal = Goal(self, element.canvas_object_name, render=self.render)
            _place_world_object(goal, unique_identifier="goal")

        world_objects_factories = {"delver": _delver_factory, "goal": _goal_factory}

        for element in self.level.map.world_objects_map.all_elements:
            world_objects_factories[element.name](element)

        return world_objects_controller
