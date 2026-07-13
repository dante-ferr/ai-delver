use std::collections::HashMap;
use pyo3::prelude::*;
use rapier2d::prelude::*;

use crate::world_objects::base_delver::BaseDelver;
use crate::world_objects::base_goal::BaseGoal;
use crate::world_objects::physics_entity::PhysicsEntity;
use crate::engine::grid::TileGrid;
use crate::engine::physics_constants::PhysicsConstants;
use crate::engine::physics_world::PhysicsWorld;

#[pyclass]
pub struct RustPhysicsEngine {
    grid: TileGrid,
    entities: HashMap<String, PhysicsEntity>,
    goal: BaseGoal,
    consts: PhysicsConstants,
    world: PhysicsWorld,
}

#[pymethods]
impl RustPhysicsEngine {
    #[new]
    pub fn new(
        width: usize,
        height: usize,
        solid_tiles: Vec<(usize, usize)>,
        goal_tiles: Vec<(usize, usize)>,
        start_x: f32,
        start_y: f32,
        tile_size: f32,
    ) -> Self {
        let consts = PhysicsConstants::default();
        let mut grid = TileGrid::new(width, height, tile_size);
        let mut world = PhysicsWorld::new();

        // Create player body (Dynamic body with rotation locked and CCD enabled)
        let player_body = RigidBodyBuilder::dynamic()
            .translation(vector![start_x, start_y])
            .lock_rotations()
            .additional_mass(100.0)
            .ccd_enabled(true)
            .build();
        let player_body_handle = world.rigid_bodies.insert(player_body);

        let half_w = consts.player_width / 2.0;
        let half_h = consts.player_height / 2.0;
        let border_radius = 0.2;
        let player_collider = ColliderBuilder::round_cuboid(
            half_w - border_radius,
            half_h - border_radius,
            border_radius,
        )
        .density(0.0)
        .friction(0.0)
        .restitution(0.0)
        .build();
        world.colliders.insert_with_parent(player_collider, player_body_handle, &mut world.rigid_bodies);

        // Add static colliders for solid tiles by merging contiguous segments in each row
        let half_tile = tile_size / 2.0;
        let mut rows: std::collections::HashMap<i32, Vec<i32>> = std::collections::HashMap::new();
        for (x, y) in solid_tiles {
            if goal_tiles.contains(&(x, y)) {
                continue;
            }
            grid.set(x, y, 1);
            rows.entry(y as i32).or_default().push(x as i32);
        }

        for (y, mut xs) in rows {
            xs.sort_unstable();
            let mut i = 0;
            while i < xs.len() {
                let start_x = xs[i];
                let mut end_x = start_x;
                while i + 1 < xs.len() && xs[i + 1] == end_x + 1 {
                    end_x = xs[i + 1];
                    i += 1;
                }

                let count = (end_x - start_x + 1) as f32;
                let segment_width = count * tile_size;
                let cell_left = start_x as f32 * tile_size;
                let cell_bottom = (height as f32 - y as f32 - 1.0) * tile_size;

                let cx = cell_left + segment_width / 2.0;
                let cy = cell_bottom + half_tile;

                let tile_collider = ColliderBuilder::cuboid(segment_width / 2.0, half_tile)
                    .translation(vector![cx, cy])
                    .friction(0.0)
                    .restitution(0.0)
                    .build();
                world.colliders.insert(tile_collider);

                i += 1;
            }
        }

        let mut goal_x = 0.0;
        let mut goal_y = 0.0;
        for (x, y) in goal_tiles {
            grid.set(x, y, 3);
            goal_x = (x as f32 + 0.5) * tile_size;
            goal_y = (height as f32 - y as f32 - 0.5) * tile_size;
        }

        let mut entities = HashMap::new();
        let mut delver = BaseDelver::new("delver".to_string(), start_x, start_y);
        delver.body_handle = player_body_handle;
        entities.insert("delver".to_string(), PhysicsEntity::Delver(delver));

        RustPhysicsEngine {
            grid,
            entities,
            goal: BaseGoal::new(goal_x, goal_y),
            consts,
            world,
        }
    }

    pub fn step(&mut self, dt: f32) -> PyResult<BaseDelver> {
        let is_delver_dead = if let Some(PhysicsEntity::Delver(ref d)) = self.entities.get("delver") {
            d.is_dead
        } else {
            false
        };

        if is_delver_dead {
            return self.get_delver();
        }

        let sub_dt = 1.0 / 60.0;
        let mut elapsed = 0.0;

        while elapsed < dt {
            let tick_dt = (dt - elapsed).min(sub_dt);
            self.tick_physics(tick_dt);
            elapsed += tick_dt;
        }

        self.get_delver()
    }

    pub fn set_entity_actions(&mut self, id: &str, action_run: f32, action_jump: bool) -> PyResult<()> {
        if let Some(entity) = self.entities.get_mut(id) {
            match entity {
                PhysicsEntity::Delver(delver) => {
                    delver.action_run = action_run;
                    delver.action_jump = action_jump;
                }
            }
            Ok(())
        } else {
            Err(pyo3::exceptions::PyKeyError::new_err(format!("Entity with id {} not found", id)))
        }
    }

    pub fn get_delver(&self) -> PyResult<BaseDelver> {
        if let Some(PhysicsEntity::Delver(ref delver)) = self.entities.get("delver") {
            Ok(delver.clone())
        } else {
            Err(pyo3::exceptions::PyKeyError::new_err("Delver entity not found"))
        }
    }

    pub fn get_goal(&self) -> BaseGoal {
        self.goal.clone()
    }

    pub fn get_goal_position(&self) -> (f32, f32) {
        (self.goal.x, self.goal.y)
    }

    pub fn get_entity_rotation(&self, id: &str) -> PyResult<f32> {
        if let Some(entity) = self.entities.get(id) {
            let rb = &self.world.rigid_bodies[entity.body_handle()];
            Ok(rb.rotation().angle())
        } else {
            Err(pyo3::exceptions::PyKeyError::new_err(format!("Entity with id {} not found", id)))
        }
    }

    pub fn get_local_view(&self, id: &str, radius: i32) -> PyResult<Vec<i32>> {
        if let Some(entity) = self.entities.get(id) {
            let (ex, ey) = match entity {
                PhysicsEntity::Delver(delver) => (delver.x, delver.y),
            };

            let tx = (ex / self.grid.tile_size).floor() as i32;
            let map_height_px = self.grid.height as f32 * self.grid.tile_size;
            let ty = ((map_height_px - ey) / self.grid.tile_size).floor() as i32;
            let mut view = Vec::new();

            for dy in -radius..=radius {
                for dx in -radius..=radius {
                    let gx = tx + dx;
                    let gy = ty + dy;
                    let tile = self.grid.get(gx, gy);
                    let cell = if gx < 0
                        || gy < 0
                        || gx >= self.grid.width as i32
                        || gy >= self.grid.height as i32
                    {
                        1
                    } else if tile == 1 {
                        1
                    } else {
                        0
                    };
                    view.push(cell);
                }
            }

            Ok(view)
        } else {
            Err(pyo3::exceptions::PyKeyError::new_err(format!("Entity with id {} not found", id)))
        }
    }
}

impl RustPhysicsEngine {
    fn tick_physics(&mut self, dt: f32) {
        self.world.query_pipeline.update(&self.world.rigid_bodies, &self.world.colliders);

        // 1. Delegate pre-step updates to all dynamic entities
        let entity_ids: Vec<String> = self.entities.keys().cloned().collect();
        for id in &entity_ids {
            let entity = self.entities.get_mut(id).unwrap();
            entity.pre_step(dt, &mut self.world, &self.consts);
        }

        // 2. Step the Physics World simulation
        let gravity = vector![0.0, self.consts.gravity];
        self.world.step(&gravity, dt);

        // Update query pipeline after step so post-step raycasts query the new positions
        self.world.query_pipeline.update(&self.world.rigid_bodies, &self.world.colliders);

        // 3. Delegate post-step updates
        for id in &entity_ids {
            let entity = self.entities.get_mut(id).unwrap();
            entity.post_step(&mut self.world, &self.consts, &self.grid);
        }
    }
}
