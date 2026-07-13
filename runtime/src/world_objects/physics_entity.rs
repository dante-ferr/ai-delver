use crate::world_objects::base_delver::BaseDelver;
use crate::engine::grid::TileGrid;
use crate::engine::physics_constants::PhysicsConstants;
use crate::engine::physics_world::PhysicsWorld;
use rapier2d::prelude::*;

pub enum PhysicsEntity {
    Delver(BaseDelver),
}

impl PhysicsEntity {
    pub fn pre_step(
        &mut self,
        dt: f32,
        world: &mut PhysicsWorld,
        consts: &PhysicsConstants,
    ) {
        match self {
            PhysicsEntity::Delver(delver) => {
                delver.pre_step(dt, world, consts);
            }
        }
    }

    pub fn post_step(
        &mut self,
        world: &mut PhysicsWorld,
        consts: &PhysicsConstants,
        grid: &TileGrid,
    ) {
        match self {
            PhysicsEntity::Delver(delver) => {
                delver.post_step(world, consts, grid);
            }
        }
    }

    pub fn id(&self) -> &str {
        match self {
            PhysicsEntity::Delver(delver) => &delver.id,
        }
    }

    pub fn body_handle(&self) -> RigidBodyHandle {
        match self {
            PhysicsEntity::Delver(delver) => delver.body_handle,
        }
    }
}
