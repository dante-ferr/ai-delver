from enum import Enum
import pyglet
from pyglet_dragonbones.skeleton import Skeleton
from .delver_body import DelverBody
import pymunk
from ..skeletal_entity import SkeletalEntity, LocomotionState
from runtime.config import ASSETS_PATH
from utils import vector_to_angle


class DelverLocomotionState(str, Enum):
    JUMP = "JUMP"


class Delver(SkeletalEntity):

    AIR_TILT_ANGLE = 20.0
    locomotion_state_enums = [DelverLocomotionState, LocomotionState]

    def __init__(self, runtime, space: pymunk.Space, render=True):
        body = DelverBody()
        space.add(body, body.shape)

        body.setup_collision_handlers()

        skeleton = self._skeleton_factory(render) if render else None
        super().__init__(runtime, body, skeleton)

    def _skeleton_factory(self, render):
        if render == True:
            delver_groups = {
                "feather": pyglet.graphics.Group(6),
                "head": pyglet.graphics.Group(5),
                "front_hand": pyglet.graphics.Group(4),
                "torso": pyglet.graphics.Group(3),
                "back_hand": pyglet.graphics.Group(2),
                "front_foot": pyglet.graphics.Group(1),
                "back_foot": pyglet.graphics.Group(0),
            }
        else:
            delver_groups = None

        skeleton = Skeleton(
            str(ASSETS_PATH / "img/sprites/delver"), groups=delver_groups, render=render
        )
        for bone in skeleton.bones.values():
            bone.transform.smoothing_enabled["scale"] = False

        return skeleton

    def run(self, dt, direction: int):
        """
        Make the delver run in a given direction. -1 = left, 1 = right
        """
        super().move(dt, vector_to_angle((direction, 0)))

    def jump(self, dt):
        jumped = self.body.jump()
        if jumped:
            self.locomotion_state = DelverLocomotionState.JUMP
            self.play_locomotion_animation()

    def draw(self, dt):
        if self.skeleton:
            self.skeleton.draw(dt)
        super().draw(dt)

    def update(self, dt):
        if self.skeleton:
            self.skeleton.position = (self.body.position.x, self.body.position.y)
            self.skeleton.update(dt)

        is_moving = self.is_moving_intentionally

        super().update(dt)

        if self.skeleton:
            self._update_tilt(is_moving)

    def _update_tilt(self, is_moving: bool):
        is_airborne = self.locomotion_state in (
            LocomotionState.GO_UP,
            LocomotionState.FALL,
            DelverLocomotionState.JUMP,
        )

        if is_airborne and is_moving:
            self.angle = (
                self.AIR_TILT_ANGLE if self.scale[0] > 0 else -self.AIR_TILT_ANGLE
            )
        else:
            self.angle = 0.0

    def _update_locomotion_state(self, is_moving: bool):
        # If we are jumping and still going up, maintain JUMP state
        if self.locomotion_state == DelverLocomotionState.JUMP:
            if self.velocity.y > 0:
                return

        super()._update_locomotion_state(is_moving)

    def _on_jump_finish(self):
        if self.locomotion_state == DelverLocomotionState.JUMP:
            if self.velocity.y > 0:
                self.locomotion_state = LocomotionState.GO_UP
            else:
                self.locomotion_state = LocomotionState.FALL
            self.play_locomotion_animation()

    def play_locomotion_animation(self):
        if self.locomotion_state == DelverLocomotionState.JUMP:
            self.run_animation("jump", on_end=self._on_jump_finish)
        else:
            super().play_locomotion_animation()
