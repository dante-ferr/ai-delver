use crate::engine::grid::TileGrid;
use crate::engine::physics_world::PhysicsWorld;
use crate::world_objects::delver::BaseDelver;
use rapier2d::prelude::*;

pub enum PhysicsEntity {
    Delver(BaseDelver),
}

impl PhysicsEntity {
    pub fn pre_step(&mut self, dt: f32, world: &mut PhysicsWorld) {
        match self {
            PhysicsEntity::Delver(delver) => {
                delver.pre_step(dt, world);
            }
        }
    }

    pub fn post_step(&mut self, world: &mut PhysicsWorld, grid: &TileGrid) {
        match self {
            PhysicsEntity::Delver(delver) => {
                delver.post_step(world, grid);
            }
        }
    }

    pub fn body_handle(&self) -> RigidBodyHandle {
        match self {
            PhysicsEntity::Delver(delver) => delver.body_handle,
        }
    }
}
