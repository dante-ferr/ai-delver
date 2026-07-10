use pyo3::prelude::*;
use rapier2d::prelude::*;
use serde::{Deserialize, Serialize};

use crate::engine::grid::TileGrid;
use crate::engine::physics_constants::PhysicsConstants;
use crate::world_objects::components::ground_detector::GroundDetector;
use crate::world_objects::components::locomotion_motor::LocomotionMotor;

#[pyclass]
#[derive(Clone, Serialize, Deserialize)]
pub struct BaseDelver {
    #[pyo3(get, set)]
    pub id: String,
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

    #[pyo3(get, set)]
    pub action_run: f32,
    #[pyo3(get, set)]
    pub action_jump: bool,

    // Reusable components
    #[serde(skip)]
    pub ground_detector: GroundDetector,
    #[serde(skip)]
    pub motor: LocomotionMotor,
    #[serde(skip)]
    pub body_handle: RigidBodyHandle,
}

#[pymethods]
impl BaseDelver {
    #[new]
    pub fn new(id: String, x: f32, y: f32) -> Self {
        BaseDelver {
            id,
            x,
            y,
            vx: 0.0,
            vy: 0.0,
            is_on_ground: false,
            is_dead: false,
            is_victory: false,
            action_run: 0.0,
            action_jump: false,
            ground_detector: GroundDetector::new(3.0, 0.05, 0.07),
            motor: LocomotionMotor::default(),
            body_handle: RigidBodyHandle::invalid(),
        }
    }
}

impl BaseDelver {
    pub fn pre_step(
        &mut self,
        dt: f32,
        rigid_body_set: &mut RigidBodySet,
        collider_set: &ColliderSet,
        query_pipeline: &QueryPipeline,
        consts: &PhysicsConstants,
    ) {
        let player_pos = self.get_translation(rigid_body_set);

        self.detect_ground(
            &player_pos,
            rigid_body_set,
            collider_set,
            query_pipeline,
            consts,
        );

        self.motor.update_timers(dt, self.is_on_ground, consts);

        self.apply_movement_input(
            dt,
            rigid_body_set,
            consts,
        );
    }

    pub fn post_step(
        &mut self,
        dt: f32,
        old_vx: f32,
        old_x: f32,
        rigid_body_set: &mut RigidBodySet,
        consts: &PhysicsConstants,
        grid: &TileGrid,
    ) {
        self.resolve_velocity_and_seams(dt, old_vx, old_x, rigid_body_set, consts);
        self.sync_state_from_physics(rigid_body_set);
        self.check_victory_and_death_conditions(grid, consts);
    }

    fn get_translation(&self, rigid_bodies: &RigidBodySet) -> Vector<f32> {
        let rb = &rigid_bodies[self.body_handle];
        *rb.translation()
    }

    fn detect_ground(
        &mut self,
        player_pos: &Vector<f32>,
        rigid_bodies: &RigidBodySet,
        colliders: &ColliderSet,
        query_pipeline: &QueryPipeline,
        consts: &PhysicsConstants,
    ) {
        self.is_on_ground = self.ground_detector.check_grounded(
            player_pos,
            consts.player_width,
            consts.player_height,
            rigid_bodies,
            colliders,
            query_pipeline,
            self.body_handle,
        );
    }

    fn apply_movement_input(
        &mut self,
        dt: f32,
        rigid_bodies: &mut RigidBodySet,
        consts: &PhysicsConstants,
    ) {
        let rb = &mut rigid_bodies[self.body_handle];
        let mut linvel = *rb.linvel();
        
        linvel.x = self.motor.calculate_horizontal_velocity(dt, self.action_run, linvel.x, consts);
        self.motor.try_jump(self.action_jump, self.is_on_ground, &mut linvel.y, consts);

        rb.set_linvel(linvel, true);
    }

    fn resolve_velocity_and_seams(
        &mut self,
        dt: f32,
        old_vx: f32,
        old_x: f32,
        rigid_bodies: &mut RigidBodySet,
        consts: &PhysicsConstants,
    ) {
        let rb = &mut rigid_bodies[self.body_handle];
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
    }

    fn sync_state_from_physics(&mut self, rigid_bodies: &RigidBodySet) {
        let rb = &rigid_bodies[self.body_handle];
        let pos = *rb.translation();
        let vel = *rb.linvel();

        self.x = pos.x;
        self.y = pos.y;
        self.vx = vel.x;
        self.vy = vel.y;
    }

    fn check_victory_and_death_conditions(&mut self, grid: &TileGrid, consts: &PhysicsConstants) {
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
