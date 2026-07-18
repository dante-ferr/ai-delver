use crate::define_config;

define_config! {
    pub struct DelverConfig,
    file: "src/world_objects/delver/delver.toml",
    {
        pub player_width: f32,
        pub player_height: f32,

        pub max_vx: f32,
        pub max_vy: f32,

        pub move_force: f32,
        pub linear_damping: f32,
        pub braking_force: f32,
        pub idle_stop_speed: f32,

        pub jump_impulse: f32,
        pub jump_tolerance_max: f32,
        pub jump_cooldown_max: f32,

        pub mass: f32,

        pub border_radius: f32,
        pub collider_density: f32,
        pub collider_friction: f32,
        pub collider_restitution: f32,

        pub ray_offset_inward: f32,
        pub ray_y_offset: f32,
        pub max_toi: f32,
    }
}
