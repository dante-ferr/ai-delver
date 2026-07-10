from enum import Enum
from typing import Optional, TYPE_CHECKING

import pyglet
from pyglet_dragonbones.skeleton import Skeleton

from .skeletal_entity import SkeletalEntity, LocomotionState
from runtime.config import ASSETS_PATH
from runtime.utils import vector_to_angle

if TYPE_CHECKING:
    from runtime.runtime import Runtime


class DelverLocomotionState(str, Enum):
    """Extended locomotion states specific to the Delver character."""
    JUMP = "JUMP"


class Delver(SkeletalEntity):
    """
    The player character for the visual (Pyglet) client.

    Physics are driven entirely by the Rust engine exposed through `runtime.physics_engine`.
    This class is responsible for:
      - Buffering pending input (`pending_run`, `pending_jump`)
      - Driving DragonBones skeleton animation from physics state
      - Air-tilt visual effect
    """

    AIR_TILT_ANGLE = 20.0
    MAX_SPEED = (500.0, 1000.0)

    def __init__(self, runtime: "Runtime", render: bool = True):
        skeleton = self._build_skeleton(render) if render else None
        super().__init__(runtime, skeleton=skeleton)

        self._physics_engine = runtime.physics_engine
        self.base_object = self._physics_engine.get_delver()
        self._spawn_based_id = "delver"
        self.pending_run: float = 0.0
        self.pending_jump: bool = False

    def _build_skeleton(self, render: bool) -> Optional[Skeleton]:
        groups = (
            {
                "feather": pyglet.graphics.Group(6),
                "head": pyglet.graphics.Group(5),
                "front_hand": pyglet.graphics.Group(4),
                "torso": pyglet.graphics.Group(3),
                "back_hand": pyglet.graphics.Group(2),
                "front_foot": pyglet.graphics.Group(1),
                "back_foot": pyglet.graphics.Group(0),
            }
            if render
            else None
        )
        skeleton = Skeleton(
            str(ASSETS_PATH / "img/sprites/delver"), groups=groups, render=render
        )
        for bone in skeleton.bones.values():
            bone.transform.smoothing_enabled["scale"] = False
            
        return skeleton

    def _state(self):
        self.base_object = self._physics_engine.get_delver()
        return self.base_object

    @property
    def position(self) -> tuple[float, float]:
        s = self._state()
        return (s.x, s.y)

    @property
    def velocity(self) -> tuple[float, float]:
        s = self._state()
        return (s.vx, s.vy)

    @property
    def is_on_ground(self) -> bool:
        return self._state().is_on_ground

    def check_collision(self, other) -> bool:
        return self._state().is_victory

    def run(self, dt: float, direction: int):
        self.pending_run = float(direction)
        self.is_moving_intentionally = True
        if self.skeleton:
            self.move_angle = vector_to_angle((direction, 0))
            self.apply_move_visuals()

    def jump(self, dt: float):
        self.pending_jump = True
        self.locomotion_state = DelverLocomotionState.JUMP
        self.play_locomotion_animation()

    def update(self, dt: float):
        s = self._state()
        if self.skeleton:
            self.skeleton.position = (s.x, s.y)
            self.skeleton.update(dt)

        is_moving = self.is_moving_intentionally
        self.is_moving_intentionally = False

        if not self.in_replay:
            self._update_locomotion(s, is_moving)

    def draw(self, dt: float):
        if self.skeleton:
            self.skeleton.draw(dt)

    def _update_locomotion(self, state, is_moving: bool):
        # Maintain JUMP state while still rising
        if self.locomotion_state == DelverLocomotionState.JUMP and state.vy > 0:
            return

        self.update_locomotion_state(
            is_on_ground=state.is_on_ground,
            vy=state.vy,
            is_moving=is_moving,
        )

        if self.skeleton:
            self._update_tilt(state, is_moving)

    def _update_tilt(self, state, is_moving: bool):
        is_airborne = self.locomotion_state in (
            LocomotionState.GO_UP,
            LocomotionState.FALL,
            DelverLocomotionState.JUMP,
        )
        if is_airborne and is_moving:
            self.angle = self.AIR_TILT_ANGLE if self.scale[0] > 0 else -self.AIR_TILT_ANGLE
        else:
            self.angle = 0.0

    def play_locomotion_animation(self):
        if self.locomotion_state == DelverLocomotionState.JUMP:
            self.run_animation("jump", on_end=self._on_jump_finish)
        else:
            super().play_locomotion_animation()

    def _on_jump_finish(self):
        if self.locomotion_state == DelverLocomotionState.JUMP:
            s = self._state()
            if s.vy <= 0:
                self.locomotion_state = LocomotionState.FALL
