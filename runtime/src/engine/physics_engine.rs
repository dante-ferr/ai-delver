use pyo3::prelude::*;
use rapier2d::prelude::*;

use crate::world_objects::base_delver::BaseDelver;
use crate::world_objects::base_goal::BaseGoal;
use crate::engine::grid::TileGrid;
use crate::engine::physics_constants::PhysicsConstants;
use crate::engine::physics_world::PhysicsWorld;

#[pyclass]
pub struct RustPhysicsEngine {
    grid: TileGrid,
    delver: BaseDelver,
    goal: BaseGoal,
    consts: PhysicsConstants,
    world: PhysicsWorld,
    player_body_handle: RigidBodyHandle,
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
            .additional_mass(1.0)
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
        .friction(0.0)
        .restitution(0.0)
        .build();
        world.colliders.insert_with_parent(player_collider, player_body_handle, &mut world.rigid_bodies);

        // Add static colliders for solid tiles
        let half_tile = tile_size / 2.0;
        for (x, y) in solid_tiles {
            if goal_tiles.contains(&(x, y)) {
                continue;
            }
            grid.set(x, y, 1);
            let cell_left = x as f32 * tile_size;
            let cell_bottom = (height as f32 - y as f32 - 1.0) * tile_size;
            let cx = cell_left + half_tile;
            let cy = cell_bottom + half_tile;

            let tile_collider = ColliderBuilder::cuboid(half_tile, half_tile)
                .translation(vector![cx, cy])
                .friction(0.0)
                .restitution(0.0)
                .build();
            world.colliders.insert(tile_collider);
        }

        let mut goal_x = 0.0;
        let mut goal_y = 0.0;
        for (x, y) in goal_tiles {
            grid.set(x, y, 3);
            goal_x = (x as f32 + 0.5) * tile_size;
            goal_y = (height as f32 - y as f32 - 0.5) * tile_size;
        }

        RustPhysicsEngine {
            grid,
            delver: BaseDelver::new(start_x, start_y),
            goal: BaseGoal::new(goal_x, goal_y),
            consts,
            world,
            player_body_handle,
        }
    }

    pub fn step(&mut self, dt: f32, action_run: f32, action_jump: bool) -> BaseDelver {
        if self.delver.is_dead {
            return self.delver.clone();
        }

        let sub_dt = 1.0 / 60.0;
        let mut elapsed = 0.0;

        while elapsed < dt {
            let tick_dt = (dt - elapsed).min(sub_dt);
            self.tick_physics(tick_dt, action_run, action_jump);
            elapsed += tick_dt;
        }

        self.delver.clone()
    }

    pub fn get_local_view(&self, radius: i32) -> Vec<i32> {
        let tx = (self.delver.x / self.grid.tile_size).floor() as i32;
        let map_height_px = self.grid.height as f32 * self.grid.tile_size;
        let ty = ((map_height_px - self.delver.y) / self.grid.tile_size).floor() as i32;
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

        view
    }

    pub fn get_delver(&self) -> BaseDelver {
        self.delver.clone()
    }

    pub fn get_goal(&self) -> BaseGoal {
        self.goal.clone()
    }

    pub fn get_goal_position(&self) -> (f32, f32) {
        (self.goal.x, self.goal.y)
    }

    pub fn get_player_rotation(&self) -> f32 {
        let rb = &self.world.rigid_bodies[self.player_body_handle];
        rb.rotation().angle()
    }
}

impl RustPhysicsEngine {
    fn tick_physics(&mut self, dt: f32, action_run: f32, action_jump: bool) {
        self.world.query_pipeline.update(&self.world.rigid_bodies, &self.world.colliders);

        let old_vx = {
            let rb = &self.world.rigid_bodies[self.player_body_handle];
            rb.linvel().x
        };
        let old_x = {
            let rb = &self.world.rigid_bodies[self.player_body_handle];
            rb.translation().x
        };

        // 1. Delegate pre-step updates to the BaseDelver
        self.delver.pre_step(
            dt,
            action_run,
            action_jump,
            &mut self.world.rigid_bodies,
            &self.world.colliders,
            &self.world.query_pipeline,
            self.player_body_handle,
            &self.consts,
        );

        // 2. Step the Physics World simulation
        let gravity = vector![0.0, self.consts.gravity];
        self.world.step(&gravity, dt);

        // 3. Delegate post-step updates and velocity restoration to the BaseDelver
        self.delver.post_step(
            dt,
            old_vx,
            old_x,
            &mut self.world.rigid_bodies,
            self.player_body_handle,
            &self.consts,
            &self.grid,
        );
    }
}
