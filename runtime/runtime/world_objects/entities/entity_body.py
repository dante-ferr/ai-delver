import pymunk
from .entity import EntityState
import math
from pymunk import Vec2d

class EntityBody(pymunk.Body):
    MOVE_FORCE: float
    LINEAR_DAMPING: float
    BRAKING_FORCE: float
    MIN_VELOCITY_TO_BRAKE = 10.0
    KNOCKBACK_FORCE_THRESHOLD = 100000.0
    TUMBLING_FORCE_THRESHOLD = 250000.0
    GROUND_THRESHOLD = 0.7

    def __init__(self, mass: float = 0, moment: float = 0):
        """
        A Body object that holds the physics representation of an entity.
        """
        super().__init__(mass, moment)

        # Assign constants to instance variables for per-instance modification.
        self.move_force = self.MOVE_FORCE
        self.braking_force = self.BRAKING_FORCE
        self.min_velocity_to_brake = self.MIN_VELOCITY_TO_BRAKE

    def setup_collision_handlers(self):
        if not self.space:
            raise ValueError("Space not set for the entity's body.")
        collision_handler = self.space.add_collision_handler(1, 2)
        collision_handler.pre_solve = self._on_collision_pre_solve

    def _on_collision_pre_solve(self, arbiter, space, data):
        if self.entity.state != EntityState.NORMAL:
            self.entity.return_to_normal_state()
        return True

    def move(self, move_angle: float):
        move_direction = Vec2d(1, 0).rotated(math.radians(move_angle))
        force_vector = move_direction * self.move_force

        # Apply braking force to change direction faster when moving opposite to current velocity.
        if self.velocity.x * move_direction.x < 0:
            braking_direction_x = (
                -self.velocity.x / abs(self.velocity.x) if self.velocity.x != 0 else 0
            )
            braking_force_vector = Vec2d(braking_direction_x * self.braking_force, 0)
            self.apply_force_at_local_point(braking_force_vector)

        self.apply_force_at_local_point(force_vector)

    def apply_damping(self):
        """Apply damping only to the horizontal component of velocity."""
        horizontal_velocity = Vec2d(self.velocity.x, 0)
        damping_force = -horizontal_velocity * self.LINEAR_DAMPING
        self.apply_force_at_local_point(damping_force)

    def brake(self):
        """Brakes horizontal movement while preserving vertical velocity."""
        if abs(self.velocity.x) > self.min_velocity_to_brake:
            braking_direction_x = (
                -self.velocity.x / abs(self.velocity.x) if self.velocity.x != 0 else 0
            )
            braking_vector_x = Vec2d(braking_direction_x * self.braking_force, 0)
            self.apply_force_at_local_point(braking_vector_x)
        else:
            # If horizontal velocity is very low, set it to zero.
            self.velocity = Vec2d(0, self.velocity.y)
            self.angular_velocity = 0

    def receive_impact(self, impulse_vector: Vec2d):
        self.apply_impulse_at_local_point(impulse_vector)

    def update(self, dt):
        pass

    @property
    def is_on_ground(self) -> bool:
        """
        Checks if the entity is on the ground using a segment query (raycast) downwards.
        """
        if self.space == None:
            return False

        if not hasattr(self, "shape") or self.shape is None:
            return False

        # 1. Check physical contacts (Arbiters)
        # This ensures that if the physics engine supports the entity, we consider it on ground.
        # This fixes the issue where the entity is standing on the very edge of a ledge.
        is_touching_ground = False

        def check_arbiter(arbiter):
            nonlocal is_touching_ground
            if is_touching_ground:
                return

            n = arbiter.contact_point_set.normal
            # Normal points from shapes[0] to shapes[1]
            if arbiter.shapes[0] == self.shape:
                # Body is first. Normal points Body -> Other. We want Down (y < -threshold).
                if n.y < -self.GROUND_THRESHOLD:
                    is_touching_ground = True
            else:
                # Body is second. Normal points Other -> Body. We want Up (y > threshold).
                if n.y > self.GROUND_THRESHOLD:
                    is_touching_ground = True

        self.each_arbiter(check_arbiter)
        if is_touching_ground:
            return True

        # 2. Raycast fallback
        # This handles cases where we are slightly above ground (coyote time, landing detection).
        bb = self.shape.cache_bb()
        start_y = bb.bottom + 1.0
        end_y = bb.bottom - 2.0  # Reduced distance to prevent false positives in air

        width = bb.right - bb.left
        inset = 1.0  # Restored inset to avoid wall edges
        x_checks = [bb.left + inset, (bb.left + bb.right) / 2, bb.right - inset]

        for x in x_checks:
            start = Vec2d(x, start_y)
            end = Vec2d(x, end_y)

            query = self.space.segment_query_first(
                start, end, 1.0, pymunk.ShapeFilter(mask=pymunk.ShapeFilter.ALL_MASKS())
            )

            if query and query.shape != self.shape:
                if query.normal.y > self.GROUND_THRESHOLD:
                    return True

        return False
