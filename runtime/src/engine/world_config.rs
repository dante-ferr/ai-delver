use crate::define_config;

define_config! {
    pub struct WorldConfig,
    file: "src/engine/world.toml",
    {
        pub gravity: f32,
        pub physics_fps: f32,

        pub tile_friction: f32,
        pub tile_restitution: f32,

        pub num_solver_iterations: usize,
        pub num_additional_friction_iterations: usize,
        pub num_internal_pgs_iterations: usize,
    }
}
