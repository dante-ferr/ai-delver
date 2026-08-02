use crate::world_objects::delver::DelverConfig;

#[derive(Clone, Default)]
pub struct LocomotionMotor {
    pub jump_tolerance_timer: f32,
    pub jump_cooldown_timer: f32,
    /// Previous frame's Jump hold — takeoff is rising-edge only (no hold-to-bunnyhop).
    jump_held_prev: bool,
    /// True after takeoff until Jump is released (cut) or ascent ends (vy <= 0).
    jump_cut_armed: bool,
}

impl LocomotionMotor {
    pub fn update_timers(&mut self, dt: f32, is_on_ground: bool, config: &DelverConfig) {
        if self.jump_cooldown_timer > 0.0 {
            self.jump_cooldown_timer -= dt;
        }

        if is_on_ground {
            self.jump_tolerance_timer = config.jump_tolerance_max;
        } else if self.jump_tolerance_timer > 0.0 {
            self.jump_tolerance_timer -= dt;
        }
    }

    pub fn calculate_horizontal_velocity(
        &self,
        dt: f32,
        action_run: f32,
        current_vx: f32,
        config: &DelverConfig,
    ) -> f32 {
        let mut force_x = 0.0;

        if action_run != 0.0 {
            force_x += action_run * config.move_force;
            if current_vx * action_run < 0.0 {
                let dir = if current_vx > 0.0 { -1.0 } else { 1.0 };
                force_x += dir * config.braking_force;
            }
            force_x -= current_vx * config.linear_damping;
        } else {
            if current_vx.abs() > config.idle_stop_speed {
                let dir = if current_vx > 0.0 { -1.0 } else { 1.0 };
                force_x += dir * config.braking_force;
            } else {
                return 0.0;
            }
        }

        let new_vx = current_vx + force_x * dt;
        new_vx.clamp(-config.max_vx, config.max_vx)
    }

    /// Rising-edge takeoff; early Jump release cuts upward velocity for short hops.
    pub fn try_jump(
        &mut self,
        action_jump: bool,
        is_on_ground: bool,
        current_vy: &mut f32,
        config: &DelverConfig,
    ) -> bool {
        let jump_pressed = action_jump && !self.jump_held_prev;
        let can_jump = is_on_ground || self.jump_tolerance_timer > 0.0;
        let mut took_off = false;

        if jump_pressed && self.jump_cooldown_timer <= 0.0 && can_jump {
            *current_vy = config.jump_impulse;
            self.jump_cooldown_timer = config.jump_cooldown_max;
            self.jump_tolerance_timer = 0.0;
            self.jump_cut_armed = true;
            took_off = true;
        } else if self.jump_cut_armed && !action_jump && *current_vy > 0.0 {
            *current_vy *= config.jump_cut_multiplier;
            self.jump_cut_armed = false;
        }

        if *current_vy <= 0.0 {
            self.jump_cut_armed = false;
        }

        self.jump_held_prev = action_jump;
        took_off
    }
}
