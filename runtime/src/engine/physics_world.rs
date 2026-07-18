use rapier2d::prelude::*;

use crate::engine::world_config::WorldConfig;

pub struct PhysicsWorld {
    pub pipeline: PhysicsPipeline,
    pub island_manager: IslandManager,
    pub broad_phase: BroadPhase,
    pub narrow_phase: NarrowPhase,
    pub rigid_bodies: RigidBodySet,
    pub colliders: ColliderSet,
    pub impulse_joints: ImpulseJointSet,
    pub multibody_joints: MultibodyJointSet,
    pub ccd_solver: CCDSolver,
    pub query_pipeline: QueryPipeline,
}

impl PhysicsWorld {
    pub fn new() -> Self {
        PhysicsWorld {
            pipeline: PhysicsPipeline::new(),
            island_manager: IslandManager::new(),
            broad_phase: BroadPhase::new(),
            narrow_phase: NarrowPhase::new(),
            rigid_bodies: RigidBodySet::new(),
            colliders: ColliderSet::new(),
            impulse_joints: ImpulseJointSet::new(),
            multibody_joints: MultibodyJointSet::new(),
            ccd_solver: CCDSolver::new(),
            query_pipeline: QueryPipeline::new(),
        }
    }

    pub fn step(&mut self, gravity: &Vector<f32>, dt: f32, world_config: &WorldConfig) {
        let mut integration_parameters = IntegrationParameters::default();
        integration_parameters.dt = dt;
        integration_parameters.num_solver_iterations =
            std::num::NonZeroUsize::new(world_config.num_solver_iterations.max(1)).unwrap();
        integration_parameters.num_additional_friction_iterations =
            world_config.num_additional_friction_iterations;
        integration_parameters.num_internal_pgs_iterations =
            world_config.num_internal_pgs_iterations;
        let physics_hooks = ();
        let event_handler = ();

        self.pipeline.step(
            gravity,
            &integration_parameters,
            &mut self.island_manager,
            &mut self.broad_phase,
            &mut self.narrow_phase,
            &mut self.rigid_bodies,
            &mut self.colliders,
            &mut self.impulse_joints,
            &mut self.multibody_joints,
            &mut self.ccd_solver,
            Some(&mut self.query_pipeline),
            &physics_hooks,
            &event_handler,
        );
    }
}
