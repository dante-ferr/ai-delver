from enum import Enum
from typing import TYPE_CHECKING, Literal, Callable, Optional
from .entity import Entity

if TYPE_CHECKING:
    from pyglet_dragonbones.skeleton import Skeleton


class LocomotionState(str, Enum):
    IDLE = "IDLE"
    RUN = "RUN"
    GO_UP = "GO_UP"
    FALL = "FALL"
    LAND = "LAND"


class SkeletalEntity(Entity):
    LAND_ANIMATION_REQUIRED_FALLING_SPEED = -250.0
    locomotion_state_enums = [LocomotionState]

    def __init__(self, runtime, body, skeleton: Optional["Skeleton"] = None):
        super().__init__(runtime, body)
        self.skeleton = skeleton
        self._locomotion_state = LocomotionState.IDLE
        self.previous_on_air_velocity = (0, 0)

        self.move_angle: None | float = None

    def move(self, dt, move_angle: float):
        super().move(dt, move_angle)

        # The move angle is saved to capture the entity's intention to generate precise replays
        self.move_angle = move_angle

        if self.skeleton:
            self.apply_move_visuals()

    def apply_move_visuals(self):
        if self.move_angle == None:
            return

        if self.move_angle > 270 or self.move_angle < 90:
            self.scale = (1, 1)
        elif self.move_angle > 90 and self.move_angle < 270:
            self.scale = (-1, 1)

    def stand(self):
        """Make the skeletal entity stand."""
        super().stand()

    def update(self, dt):
        # Capture intention before super().update() resets it
        is_moving = self.is_moving_intentionally

        super().update(dt)

        # The replay sets the locomotion state to ensure determinism, so we don't conditionally
        # update it
        if not self.in_replay:
            self._update_locomotion_state(is_moving)

        if not self.is_on_ground:
            # Only update if velocity is significant. This prevents overwriting the
            # falling velocity with 0 on the specific frame where the physics has stopped
            # the body (collision) but the raycast (is_on_ground) hasn't updated yet.
            if abs(self.velocity.y) > 1.0:
                self.previous_on_air_velocity = (self.velocity.x, self.velocity.y)

    @property
    def locomotion_state(self):
        return self._locomotion_state

    @locomotion_state.setter
    def locomotion_state(self, value):
        if self._locomotion_state != value:
            self._locomotion_state = value
            if self.skeleton:
                self.play_locomotion_animation()

    def _update_locomotion_state(self, is_moving: bool):
        new_state = self.locomotion_state

        if self.is_on_ground:
            if self.locomotion_state in (LocomotionState.GO_UP, LocomotionState.FALL):
                if (
                    self.previous_on_air_velocity[1]
                    <= self.LAND_ANIMATION_REQUIRED_FALLING_SPEED
                ):
                    new_state = LocomotionState.LAND
                else:
                    new_state = (
                        LocomotionState.RUN if is_moving else LocomotionState.IDLE
                    )
            elif self.locomotion_state == LocomotionState.LAND:
                # if is_moving:
                #    new_state = LocomotionState.RUN
                pass
            else:
                new_state = LocomotionState.RUN if is_moving else LocomotionState.IDLE
        else:
            new_state = (
                LocomotionState.GO_UP if self.velocity.y > 0 else LocomotionState.FALL
            )

        self.locomotion_state = new_state

    def resolve_locomotion_state(self, state_name: str):
        for enum_cls in self.locomotion_state_enums:
            try:
                return enum_cls(state_name)
            except ValueError:
                continue
        return state_name

    def play_locomotion_animation(self):
        if self.locomotion_state == LocomotionState.IDLE:
            self.run_animation("idle")
        elif self.locomotion_state == LocomotionState.RUN:
            self.run_animation("run")
        elif self.locomotion_state == LocomotionState.GO_UP:
            self.run_animation("go_up")
        elif self.locomotion_state == LocomotionState.FALL:
            self.run_animation("fall")
        elif self.locomotion_state == LocomotionState.LAND:
            self.run_animation("land", on_end=self._on_land_finish)

    def _on_land_finish(self):
        if self.locomotion_state == LocomotionState.LAND:
            self.locomotion_state = LocomotionState.IDLE

    @property
    def angle(self):
        return self.skeleton.angle if self.skeleton else 0.0

    @angle.setter
    def angle(self, angle: float):
        if self.skeleton:
            self.skeleton.angle = angle

    @property
    def scale(self):
        return self.skeleton.scale if self.skeleton else (1.0, 1.0)

    @scale.setter
    def scale(self, scale: tuple[float, float]):
        if self.skeleton:
            self.skeleton.scale = scale

    @property
    def target_angle(self) -> float | None:
        return self.skeleton.target_angle if self.skeleton else None

    @target_angle.setter
    def target_angle(self, angle: float):
        """Set the target angle of the skeletal entity."""
        if self.skeleton:
            self.skeleton.target_angle = angle

    def run_animation(
        self,
        animation_name: str | None,
        starting_frame=0,
        speed=1,
        on_end: Literal["_loop"] | Callable = "_loop",
    ):
        """Run an animation on the skeletal entity."""
        if self.skeleton:
            self.skeleton.run_animation(animation_name, starting_frame, speed, on_end)

    def cleanup(self):
        if hasattr(self, "skeleton") and self.skeleton:
            del self.skeleton.batch
            del self.skeleton
