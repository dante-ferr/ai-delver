from ..entity_body import EntityBody
import pymunk
from pymunk import Vec2d


class DelverBody(EntityBody):
    MOVE_FORCE = 2300.0
    LINEAR_DAMPING = 15.0
    BRAKING_FORCE = 900.0
    JUMP_IMPULSE = 370.0

    COLLISION_MASK_SIZE = (10.0, 38.0)
    MASS = 1.0

    JUMP_TOLERANCE_TIMER_MAX = 0.105
    JUMP_COOLDOWN_MAX = 0.2

    def __init__(self):
        width, height = self.COLLISION_MASK_SIZE

        # Reverted to sharp corners as requested
        left = -width / 2
        right = width / 2
        bottom = 0
        top = height

        vertices = [(left, bottom), (right, bottom), (right, top), (left, top)]

        center_of_gravity = (0, bottom)
        super().__init__(self.MASS, float("inf"))

        self.shape = pymunk.Poly(
            self,
            vertices,
            transform=pymunk.Transform(
                tx=center_of_gravity[0], ty=center_of_gravity[1]
            ),
        )
        self.shape.collision_type = 1
        self.jump_tolerance_timer = 0
        self.jump_cooldown_timer = 0
        self.jumped = False

    def jump(self):
        if self.jump_cooldown_timer > 0:
            return False

        if self.is_on_ground or self.jump_tolerance_timer > 0:
            self.jumped = True

            # Check if we are physically touching something (Arbiter exists)
            has_contact = False

            def check_contact(arbiter):
                nonlocal has_contact
                has_contact = True

            self.each_arbiter(check_contact)

            # GAP FIX:
            # If we are allowed to jump (Raycast/Coyote) but have NO physical contact,
            # and we are falling, we are in the "Raycast Buffer Gap".
            # In this specific case, we stabilize the jump to prevent the "Small Jump" bug.
            # Otherwise (if we have contact), we respect existing momentum (Realism).
            if not has_contact and self.velocity.y < 0:
                self.velocity = Vec2d(self.velocity.x, 0)

            impulse = (0, self.JUMP_IMPULSE)
            self.apply_impulse_at_local_point(impulse, (0, 0))
            self.jump_tolerance_timer = 0
            self.jump_cooldown_timer = self.JUMP_COOLDOWN_MAX

        return self.jumped

    def update(self, dt):
        super().update(dt)

        if self.jump_cooldown_timer > 0:
            self.jump_cooldown_timer -= dt

        if self.is_on_ground and not self.jumped:
            self.jump_tolerance_timer = self.JUMP_TOLERANCE_TIMER_MAX
        else:
            self.jump_tolerance_timer = max(0, self.jump_tolerance_timer - dt)

        self.jumped = False
