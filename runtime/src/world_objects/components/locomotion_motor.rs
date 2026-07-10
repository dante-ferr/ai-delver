use crate::engine::physics_constants::PhysicsConstants;

#[derive(Clone, Default)]
pub struct LocomotionMotor {
    pub jump_tolerance_timer: f32,
    pub jump_cooldown_timer: f32,
}

impl LocomotionMotor {
    pub fn update_timers(&mut self, dt: f32, is_on_ground: bool, consts: &PhysicsConstants) {
        if self.jump_cooldown_timer > 0.0 {
            self.jump_cooldown_timer -= dt;
        }

        if is_on_ground {
            self.jump_tolerance_timer = consts.jump_tolerance_max;
        } else if self.jump_tolerance_timer > 0.0 {
            self.jump_tolerance_timer -= dt;
        }
    }

    pub fn calculate_horizontal_velocity(
        &self,
        dt: f32,
        action_run: f32,
        current_vx: f32,
        consts: &PhysicsConstants,
    ) -> f32 {
        let mut force_x = 0.0;

        if action_run != 0.0 {
            force_x += action_run * consts.move_force;
            if current_vx * action_run < 0.0 {
                let dir = if current_vx > 0.0 { -1.0 } else { 1.0 };
                force_x += dir * consts.braking_force;
            }
            force_x -= current_vx * consts.linear_damping;
        } else {
            if current_vx.abs() > 10.0 {
                let dir = if current_vx > 0.0 { -1.0 } else { 1.0 };
                force_x += dir * consts.braking_force;
            } else {
                return 0.0;
            }
        }

        let new_vx = current_vx + force_x * dt;
        new_vx.clamp(-consts.max_vx, consts.max_vx)
    }

    pub fn try_jump(
        &mut self,
        action_jump: bool,
        is_on_ground: bool,
        current_vy: &mut f32,
        consts: &PhysicsConstants,
    ) -> bool {
        let can_jump = is_on_ground || self.jump_tolerance_timer > 0.0;
        if action_jump && self.jump_cooldown_timer <= 0.0 && can_jump {
            *current_vy = consts.jump_impulse;
            self.jump_cooldown_timer = consts.jump_cooldown_max;
            self.jump_tolerance_timer = 0.0;
            true
        } else {
            false
        }
    }
}
