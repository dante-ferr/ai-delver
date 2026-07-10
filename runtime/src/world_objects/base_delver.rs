use pyo3::prelude::*;
use rapier2d::prelude::*;
use serde::{Deserialize, Serialize};

use crate::engine::grid::TileGrid;
use crate::engine::physics_constants::PhysicsConstants;

#[pyclass]
#[derive(Clone, Serialize, Deserialize)]
pub struct BaseDelver {
    #[pyo3(get, set)]
    pub x: f32,
    #[pyo3(get, set)]
    pub y: f32,
    #[pyo3(get, set)]
    pub vx: f32,
    #[pyo3(get, set)]
    pub vy: f32,
    #[pyo3(get, set)]
    pub is_on_ground: bool,
    #[pyo3(get, set)]
    pub is_dead: bool,
    #[pyo3(get, set)]
    pub is_victory: bool,

    // Internal physics state not exposed to Python
    #[serde(skip)]
    pub jump_tolerance_timer: f32,
    #[serde(skip)]
    pub jump_cooldown_timer: f32,
}

#[pymethods]
impl BaseDelver {
    #[new]
    pub fn new(x: f32, y: f32) -> Self {
        BaseDelver {
            x,
            y,
            vx: 0.0,
            vy: 0.0,
            is_on_ground: false,
            is_dead: false,
            is_victory: false,
            jump_tolerance_timer: 0.0,
            jump_cooldown_timer: 0.0,
        }
    }
}

impl BaseDelver {
    pub fn pre_step(
        &mut self,
        dt: f32,
        action_run: f32,
        action_jump: bool,
        rigid_body_set: &mut RigidBodySet,
        collider_set: &ColliderSet,
        query_pipeline: &QueryPipeline,
        player_body_handle: RigidBodyHandle,
        consts: &PhysicsConstants,
    ) {
        if self.jump_cooldown_timer > 0.0 {
            self.jump_cooldown_timer -= dt;
        }

        // Query ground state
        let rb = &rigid_body_set[player_body_handle];
        let player_pos = *rb.translation();

        let left_x = player_pos.x - consts.player_width / 2.0 + 3.0;
        let right_x = player_pos.x + consts.player_width / 2.0 - 3.0;
        let ray_y = player_pos.y - consts.player_height / 2.0 + 0.05;

        let ray_dir = vector![0.0, -1.0];
        let max_toi = 0.07;

        let filter = QueryFilter::default().exclude_rigid_body(player_body_handle);

        let hit_left = query_pipeline.cast_ray(
            rigid_body_set,
            collider_set,
            &Ray::new(point![left_x, ray_y], ray_dir),
            max_toi,
            true,
            filter,
        );

        let hit_right = query_pipeline.cast_ray(
            rigid_body_set,
            collider_set,
            &Ray::new(point![right_x, ray_y], ray_dir),
            max_toi,
            true,
            filter,
        );

        let is_on_ground = hit_left.is_some() || hit_right.is_some();
        self.is_on_ground = is_on_ground;

        if is_on_ground {
            self.jump_tolerance_timer = consts.jump_tolerance_max;
        } else if self.jump_tolerance_timer > 0.0 {
            self.jump_tolerance_timer -= dt;
        }

        // Calculate forces
        let rb = &mut rigid_body_set[player_body_handle];
        let mut linvel = *rb.linvel();
        let mut force_x = 0.0;

        if action_run != 0.0 {
            force_x += action_run * consts.move_force;
            if linvel.x * action_run < 0.0 {
                let dir = if linvel.x > 0.0 { -1.0 } else { 1.0 };
                force_x += dir * consts.braking_force;
            }
            force_x -= linvel.x * consts.linear_damping;
        } else {
            if linvel.x.abs() > 10.0 {
                let dir = if linvel.x > 0.0 { -1.0 } else { 1.0 };
                force_x += dir * consts.braking_force;
            } else {
                linvel.x = 0.0;
            }
        }

        linvel.x += force_x * dt;
        linvel.x = linvel.x.clamp(-consts.max_vx, consts.max_vx);

        let can_jump = is_on_ground || self.jump_tolerance_timer > 0.0;
        if action_jump && self.jump_cooldown_timer <= 0.0 && can_jump {
            linvel.y = consts.jump_impulse;
            self.jump_cooldown_timer = consts.jump_cooldown_max;
            self.jump_tolerance_timer = 0.0;
        }

        rb.set_linvel(linvel, true);
    }

    pub fn post_step(
        &mut self,
        dt: f32,
        old_vx: f32,
        old_x: f32,
        rigid_body_set: &mut RigidBodySet,
        player_body_handle: RigidBodyHandle,
        consts: &PhysicsConstants,
        grid: &TileGrid,
    ) {
        let rb = &mut rigid_body_set[player_body_handle];
        let pos = *rb.translation();
        let mut vel = *rb.linvel();

        let dx = (pos.x - old_x).abs();
        let intended_dx = (old_vx * dt).abs();
        if intended_dx > 0.1 && dx < 0.1 * intended_dx {
            vel.x = 0.0;
        } else if self.is_on_ground {
            vel.x = old_vx;
        }

        vel.x = vel.x.clamp(-consts.max_vx, consts.max_vx);
        vel.y = vel.y.clamp(-consts.max_vy, consts.max_vy);
        rb.set_linvel(vel, true);

        // Update fields
        self.x = pos.x;
        self.y = pos.y;
        self.vx = vel.x;
        self.vy = vel.y;

        // Check victory
        let half_w = consts.player_width / 2.0;
        let half_h = consts.player_height / 2.0;
        let left = self.x - half_w;
        let right = self.x + half_w;
        let bottom = self.y - half_h;
        let top = self.y + half_h;

        let (min_tx, max_tx, min_ty, max_ty) = grid.tile_coords_for_aabb(left, right, bottom, top);
        for ty in min_ty..=max_ty {
            for tx in min_tx..=max_tx {
                if grid.get(tx as i32, ty as i32) == 3 {
                    self.is_victory = true;
                }
            }
        }

        if self.y + half_h < 0.0 {
            self.is_dead = true;
        }
    }
}
