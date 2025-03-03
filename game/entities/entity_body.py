import pymunk
from typing import Literal


class EntityBody(pymunk.Body):
    def __init__(self, mass: float = 0, moment: float = 0):
        """
        A Body object that holds the physics representation of an entity.
        """
        super().__init__(mass, moment)

    def setup_collision_handlers(self):
        """Set up collision handlers for the body."""
        if not self.space:
            raise ValueError("Space not set for the entity's body.")

        collision_handler = self.space.add_collision_handler(1, 2)
        collision_handler.pre_solve = self._on_collision_pre_solve

    def _on_collision_pre_solve(self, arbiter, space, data):
        """Callback that occurs while the collision is happening."""
        self.velocity = pymunk.Vec2d(0, 0)
        return True

    def update(self, dt):
        self.limit_speed()

    def set_damping(self, damping: float | Literal["normal"] = "normal"):
        """Set the damping of the body."""
        if damping == "normal":
            self.damping = self.normal_damping
            return
        self.damping = damping

    @property
    def max_velocity(self):
        """Get the maximum speed for the body."""
        return self._max_velocity

    @max_velocity.setter
    def max_velocity(self, value: float):
        """Set the maximum speed for the body."""
        self._max_velocity = value

    def limit_speed(self):
        """Limit the body's speed to the set maximum speed."""
        if self.max_velocity is not None:
            current_speed = self.velocity.length
            if current_speed > self.max_velocity:
                self.velocity = self.velocity.normalized() * self.max_velocity
