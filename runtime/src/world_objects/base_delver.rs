use rapier2d::prelude::*;
use serde::{Deserialize, Serialize};

#[cfg(feature = "python")]
use pyo3::prelude::*;

use crate::engine::grid::TileGrid;
use crate::engine::physics_constants::PhysicsConstants;
use crate::engine::physics_world::PhysicsWorld;
use crate::world_objects::components::ground_detector::GroundDetector;
use crate::world_objects::components::locomotion_motor::LocomotionMotor;

#[cfg_attr(feature = "python", pyclass)]
#[derive(Clone, Serialize, Deserialize)]
pub struct BaseDelver {
    pub id: String,
    pub x: f32,
    pub y: f32,
    pub vx: f32,
    pub vy: f32,
    pub is_on_ground: bool,
    pub is_dead: bool,
    pub is_victory: bool,

    pub action_run: f32,
    pub action_jump: bool,

    // Reusable components
    #[serde(skip)]
    pub(crate) ground_detector: GroundDetector,
    #[serde(skip)]
    pub(crate) motor: LocomotionMotor,
    #[serde(skip)]
    pub(crate) body_handle: RigidBodyHandle,
}

impl BaseDelver {
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
            ground_detector: GroundDetector::new(3.0, 5.0, 5.2),
            motor: LocomotionMotor::default(),
            body_handle: RigidBodyHandle::invalid(),
        }
    }
}

#[cfg(feature = "python")]
#[pyo3::pymethods]
impl BaseDelver {
    #[new]
    fn py_new(id: String, x: f32, y: f32) -> Self {
        Self::new(id, x, y)
    }

    #[getter]
    fn id(&self) -> &str {
        &self.id
    }

    #[setter]
    fn set_id(&mut self, value: String) {
        self.id = value;
    }

    #[getter]
    fn x(&self) -> f32 {
        self.x
    }

    #[setter]
    fn set_x(&mut self, value: f32) {
        self.x = value;
    }

    #[getter]
    fn y(&self) -> f32 {
        self.y
    }

    #[setter]
    fn set_y(&mut self, value: f32) {
        self.y = value;
    }

    #[getter]
    fn vx(&self) -> f32 {
        self.vx
    }

    #[setter]
    fn set_vx(&mut self, value: f32) {
        self.vx = value;
    }

    #[getter]
    fn vy(&self) -> f32 {
        self.vy
    }

    #[setter]
    fn set_vy(&mut self, value: f32) {
        self.vy = value;
    }

    #[getter]
    fn is_on_ground(&self) -> bool {
        self.is_on_ground
    }

    #[setter]
    fn set_is_on_ground(&mut self, value: bool) {
        self.is_on_ground = value;
    }

    #[getter]
    fn is_dead(&self) -> bool {
        self.is_dead
    }

    #[setter]
    fn set_is_dead(&mut self, value: bool) {
        self.is_dead = value;
    }

    #[getter]
    fn is_victory(&self) -> bool {
        self.is_victory
    }

    #[setter]
    fn set_is_victory(&mut self, value: bool) {
        self.is_victory = value;
    }

    #[getter]
    fn action_run(&self) -> f32 {
        self.action_run
    }

    #[setter]
    fn set_action_run(&mut self, value: f32) {
        self.action_run = value;
    }

    #[getter]
    fn action_jump(&self) -> bool {
        self.action_jump
    }

    #[setter]
    fn set_action_jump(&mut self, value: bool) {
        self.action_jump = value;
    }
}

impl BaseDelver {
    pub(crate) fn pre_step(
        &mut self,
        dt: f32,
        world: &mut PhysicsWorld,
        consts: &PhysicsConstants,
    ) {
        let player_pos = self.get_translation(&world.rigid_bodies);

        self.detect_ground(
            &player_pos,
            &world.rigid_bodies,
            &world.colliders,
            &world.query_pipeline,
            consts,
        );

        self.motor.update_timers(dt, self.is_on_ground, consts);

        self.apply_movement_input(dt, world, consts);
    }

    pub(crate) fn post_step(
        &mut self,
        world: &mut PhysicsWorld,
        consts: &PhysicsConstants,
        grid: &TileGrid,
    ) {
        let pos = self.get_translation(&world.rigid_bodies);
        self.detect_ground(
            &pos,
            &world.rigid_bodies,
            &world.colliders,
            &world.query_pipeline,
            consts,
        );
        self.sync_state_from_physics(&world.rigid_bodies);
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
        world: &mut PhysicsWorld,
        consts: &PhysicsConstants,
    ) {
        let rb = &mut world.rigid_bodies[self.body_handle];
        let mut linvel = *rb.linvel();

        linvel.x = self
            .motor
            .calculate_horizontal_velocity(dt, self.action_run, linvel.x, consts);
        self.motor
            .try_jump(self.action_jump, self.is_on_ground, &mut linvel.y, consts);
        rb.set_linvel(linvel, true);
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
