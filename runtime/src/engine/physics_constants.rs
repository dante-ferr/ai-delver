/// All tunable physical constants for the simulation.
/// Centralised here so they can be adjusted or made configurable without
/// touching the engine logic.
pub struct PhysicsConstants {
    // Player dimensions (pixels)
    pub player_width: f32,
    pub player_height: f32,

    // Gravity & velocity caps
    pub gravity: f32,
    pub max_vx: f32,
    pub max_vy: f32,

    // Horizontal movement
    pub move_force: f32,
    pub linear_damping: f32,
    pub braking_force: f32,

    // Jump
    pub jump_impulse: f32,
    /// How long after leaving the ground can the player still jump (coyote time)
    pub jump_tolerance_max: f32,
    /// Minimum time between consecutive jumps
    pub jump_cooldown_max: f32,
}

impl Default for PhysicsConstants {
    fn default() -> Self {
        PhysicsConstants {
            player_width: 10.0,
            player_height: 38.0,
            gravity: -1000.0,
            max_vx: 500.0,
            max_vy: 1000.0,
            move_force: 2300.0,
            linear_damping: 15.0,
            braking_force: 900.0,
            jump_impulse: 370.0,
            jump_tolerance_max: 0.105,
            jump_cooldown_max: 0.2,
        }
    }
}
