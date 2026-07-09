import math
from enum import Enum, auto
from typing import TYPE_CHECKING
from ..world_object import WorldObject
from pymunk import Vec2d

if TYPE_CHECKING:
    from .entity_body import EntityBody


class EntityState(Enum):
    """Defines the possible states of the entity."""

    NORMAL = auto()
    KNOCKBACK = auto()
    TUMBLING = auto()


class Entity(WorldObject):
    MAX_SPEED = (500.0, 1000.0)

    def __init__(self, runtime, body: "EntityBody"):
        super().__init__(runtime)
        self.body = body
        self.body.entity = self
        self.state = EntityState.NORMAL
        self.is_moving_intentionally = False

    @property
    def shape(self):
        return next(iter(self.body.shapes))

    @property
    def is_on_ground(self) -> bool:
        """Check if the entity is on the ground."""
        return self.body.is_on_ground

    def move(self, dt, move_angle: float):
        if self.state != EntityState.NORMAL:
            return
        self.is_moving_intentionally = True
        self.body.move(move_angle)

    def brake(self):
        if self.state != EntityState.NORMAL:
            return
        self.body.brake()

    def receive_impact(self, impulse_vector: Vec2d):
        impulse_magnitude = impulse_vector.length
        if impulse_magnitude >= self.body.TUMBLING_FORCE_THRESHOLD:
            self.state = EntityState.TUMBLING
            print("STATE CHANGE: TUMBLING")
        elif impulse_magnitude >= self.body.KNOCKBACK_FORCE_THRESHOLD:
            self.state = EntityState.KNOCKBACK
            print("STATE CHANGE: KNOCKBACK")
        self.body.receive_impact(impulse_vector)

    def return_to_normal_state(self):
        if self.state != EntityState.NORMAL:
            print("STATE CHANGE: NORMAL")
            self.state = EntityState.NORMAL

    def run_animation(self, animation_name: str | None):
        pass

    def stand(self):
        self.brake()

    def update(self, dt):
        if self.state == EntityState.NORMAL:
            # If the entity is not actively receiving movement commands, apply braking to its horizontal velocity.
            # Pymunk's linear_damping property handles general damping (like air resistance).
            if self.is_moving_intentionally:
                self.body.apply_damping()
            else:
                self.stand()

        self._limit_speed()

        self.is_moving_intentionally = (
            False  # Reset the flag for the next frame's input
        )

        bb = self.shape.cache_bb()
        self.bounding_box = (bb.left, bb.bottom, bb.right, bb.top)

        self.body.update(dt)

    def _limit_speed(self):
        vx, vy = self.body.velocity
        max_vx, max_vy = self.MAX_SPEED
        if abs(vx) > max_vx:
            vx = math.copysign(max_vx, vx)
        if abs(vy) > max_vy:
            vy = math.copysign(max_vy, vy)
        self.body.velocity = Vec2d(vx, vy)

    @property
    def velocity(self) -> Vec2d:
        """Get the current velocity vector of the entity."""
        return self.body.velocity

    @property
    def speed(self) -> float:
        """Get the current speed of the entity."""
        return self.body.velocity.length

    @property
    def position(self):
        return self.body.position.x, self.body.position.y

    @position.setter
    def position(self, position: tuple[float, float]):
        self._conditionally_set_spawn_based_id(position)
        self.body.position = Vec2d(position[0], position[1])

    @property
    def angle(self):
        return self.body.angle

    @angle.setter
    def angle(self, angle: float):
        self.body.angle = angle

    @property
    def target_angle(self) -> float | None:
        return None

    @target_angle.setter
    def target_angle(self, angle: float):
        pass

    def update_angle_to_target(self, dt: float):
        pass
