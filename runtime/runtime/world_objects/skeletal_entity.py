from enum import Enum
from typing import TYPE_CHECKING, Literal, Callable, Optional

from .world_object import WorldObject

if TYPE_CHECKING:
    from pyglet_dragonbones.skeleton import Skeleton


class LocomotionState(str, Enum):
    IDLE = "IDLE"
    RUN = "RUN"
    GO_UP = "GO_UP"
    FALL = "FALL"
    LAND = "LAND"


class SkeletalEntity(WorldObject):
    """
    A world object that carries an optional DragonBones skeleton for visual animation.

    Physics are provided externally (e.g. by the Rust engine). This class only
    manages locomotion-state transitions and delegates them to skeleton animations.
    """

    LAND_ANIMATION_REQUIRED_FALLING_SPEED = -250.0

    def __init__(self, runtime, skeleton: Optional["Skeleton"] = None):
        super().__init__(runtime)
        self.skeleton = skeleton
        self._locomotion_state = LocomotionState.IDLE
        self.previous_on_air_vy: float = 0.0
        self.is_moving_intentionally: bool = False
        self.move_angle: float | None = None

    @property
    def locomotion_state(self) -> LocomotionState:
        return self._locomotion_state

    @locomotion_state.setter
    def locomotion_state(self, value: LocomotionState):
        if self._locomotion_state != value:
            self._locomotion_state = value
            if self.skeleton:
                self.play_locomotion_animation()

    def update_locomotion_state(self, is_on_ground: bool, vy: float, is_moving: bool):
        """
        Derive the next locomotion state from physics state.
        Call this from your concrete subclass's `update()` method.
        """
        new_state = self._locomotion_state

        if is_on_ground:
            if self._locomotion_state in (LocomotionState.GO_UP, LocomotionState.FALL):
                if self.previous_on_air_vy <= self.LAND_ANIMATION_REQUIRED_FALLING_SPEED:
                    new_state = LocomotionState.LAND
                else:
                    new_state = LocomotionState.RUN if is_moving else LocomotionState.IDLE
            elif self._locomotion_state == LocomotionState.LAND:
                pass  # wait for land animation to finish
            else:
                new_state = LocomotionState.RUN if is_moving else LocomotionState.IDLE
        else:
            if abs(vy) > 1.0:
                self.previous_on_air_vy = vy
            new_state = LocomotionState.GO_UP if vy > 0 else LocomotionState.FALL

        self.locomotion_state = new_state

    def play_locomotion_animation(self):
        mapping = {
            LocomotionState.IDLE: "idle",
            LocomotionState.RUN: "run",
            LocomotionState.GO_UP: "go_up",
            LocomotionState.FALL: "fall",
        }
        if self._locomotion_state == LocomotionState.LAND:
            self.run_animation("land", on_end=self._on_land_finish)
        elif self._locomotion_state in mapping:
            self.run_animation(mapping[self._locomotion_state])

    def _on_land_finish(self):
        if self._locomotion_state == LocomotionState.LAND:
            self.locomotion_state = LocomotionState.IDLE

    def run_animation(
        self,
        animation_name: str | None,
        starting_frame: int = 0,
        speed: float = 1,
        on_end: "Literal['_loop'] | Callable" = "_loop",
    ):
        """Run a named animation on the attached skeleton (no-op if no skeleton)."""
        if self.skeleton:
            self.skeleton.run_animation(animation_name, starting_frame, speed, on_end)

    def apply_move_visuals(self):
        """Flip the skeleton based on horizontal move direction."""
        if self.move_angle is None or not self.skeleton:
            return
        if self.move_angle > 270 or self.move_angle < 90:
            self.scale = (1, 1)
        elif 90 < self.move_angle < 270:
            self.scale = (-1, 1)

    @property
    def angle(self) -> float:
        return self.skeleton.angle if self.skeleton else 0.0

    @angle.setter
    def angle(self, value: float):
        if self.skeleton:
            self.skeleton.angle = value

    @property
    def scale(self) -> tuple[float, float]:
        return self.skeleton.scale if self.skeleton else (1.0, 1.0)

    @scale.setter
    def scale(self, value: tuple[float, float]):
        if self.skeleton:
            self.skeleton.scale = value

    @property
    def target_angle(self) -> float | None:
        return self.skeleton.target_angle if self.skeleton else None

    @target_angle.setter
    def target_angle(self, value: float):
        if self.skeleton:
            self.skeleton.target_angle = value

    def cleanup(self):
        if hasattr(self, "skeleton") and self.skeleton:
            del self.skeleton.batch
            del self.skeleton
