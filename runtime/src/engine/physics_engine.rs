use pyo3::prelude::*;
use rapier2d::prelude::*;

use crate::world_objects::base_delver::BaseDelver;
use crate::world_objects::base_goal::BaseGoal;
use crate::engine::grid::TileGrid;
use crate::engine::physics_constants::PhysicsConstants;

#[pyclass]
pub struct RustPhysicsEngine {
    grid: TileGrid,
    delver: BaseDelver,
    goal: BaseGoal,
    consts: PhysicsConstants,

    // Rapier components
    physics_pipeline: PhysicsPipeline,
    island_manager: IslandManager,
    broad_phase: BroadPhase,
    narrow_phase: NarrowPhase,
    rigid_body_set: RigidBodySet,
    collider_set: ColliderSet,
    impulse_joint_set: ImpulseJointSet,
    multibody_joint_set: MultibodyJointSet,
    ccd_solver: CCDSolver,
    query_pipeline: QueryPipeline,

    // Handles
    player_body_handle: RigidBodyHandle,

    // Jump timers
    jump_tolerance_timer: f32,
    jump_cooldown_timer: f32,
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

        let mut rigid_body_set = RigidBodySet::new();
        let mut collider_set = ColliderSet::new();

        // Create player body (Dynamic body with rotation locked and CCD enabled)
        let player_body = RigidBodyBuilder::dynamic()
            .translation(vector![start_x, start_y])
            .lock_rotations()
            .additional_mass(1.0)
            .ccd_enabled(true)
            .build();
        let player_body_handle = rigid_body_set.insert(player_body);

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
        collider_set.insert_with_parent(player_collider, player_body_handle, &mut rigid_body_set);

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
            collider_set.insert(tile_collider);
        }

        let mut goal_x = 0.0;
        let mut goal_y = 0.0;
        for (x, y) in goal_tiles {
            grid.set(x, y, 3);
            goal_x = (x as f32 + 0.5) * tile_size;
            goal_y = (height as f32 - y as f32 - 0.5) * tile_size;
        }

        let physics_pipeline = PhysicsPipeline::new();
        let island_manager = IslandManager::new();
        let broad_phase = BroadPhase::new();
        let narrow_phase = NarrowPhase::new();
        let impulse_joint_set = ImpulseJointSet::new();
        let multibody_joint_set = MultibodyJointSet::new();
        let ccd_solver = CCDSolver::new();
        let query_pipeline = QueryPipeline::new();

        RustPhysicsEngine {
            grid,
            delver: BaseDelver::new(start_x, start_y),
            goal: BaseGoal::new(goal_x, goal_y),
            consts,
            physics_pipeline,
            island_manager,
            broad_phase,
            narrow_phase,
            rigid_body_set,
            collider_set,
            impulse_joint_set,
            multibody_joint_set,
            ccd_solver,
            query_pipeline,
            player_body_handle,
            jump_tolerance_timer: 0.0,
            jump_cooldown_timer: 0.0,
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
        let rb = &self.rigid_body_set[self.player_body_handle];
        rb.rotation().angle()
    }
}

impl RustPhysicsEngine {
    fn tick_physics(&mut self, dt: f32, action_run: f32, action_jump: bool) {
        // 1. Update jump timers
        if self.jump_cooldown_timer > 0.0 {
            self.jump_cooldown_timer -= dt;
        }

        // Query ground state before taking a step
        self.query_pipeline.update(&self.rigid_body_set, &self.collider_set);
        let rb = &self.rigid_body_set[self.player_body_handle];
        let player_pos = *rb.translation();

        let left_x = player_pos.x - self.consts.player_width / 2.0 + 3.0;
        let right_x = player_pos.x + self.consts.player_width / 2.0 - 3.0;
        let ray_y = player_pos.y - self.consts.player_height / 2.0 + 0.05;

        let ray_dir = vector![0.0, -1.0];
        let max_toi = 0.07; // 0.05 internal offset + 0.02 buffer below feet

        let filter = QueryFilter::default().exclude_rigid_body(self.player_body_handle);

        let hit_left = self.query_pipeline.cast_ray(
            &self.rigid_body_set,
            &self.collider_set,
            &Ray::new(point![left_x, ray_y], ray_dir),
            max_toi,
            true,
            filter,
        );

        let hit_right = self.query_pipeline.cast_ray(
            &self.rigid_body_set,
            &self.collider_set,
            &Ray::new(point![right_x, ray_y], ray_dir),
            max_toi,
            true,
            filter,
        );

        let is_on_ground = hit_left.is_some() || hit_right.is_some();

        if is_on_ground {
            self.jump_tolerance_timer = self.consts.jump_tolerance_max;
        } else if self.jump_tolerance_timer > 0.0 {
            self.jump_tolerance_timer -= dt;
        }

        // 2. Fetch and calculate horizontal forces / damping
        let rb = &mut self.rigid_body_set[self.player_body_handle];
        let mut linvel = *rb.linvel();
        let mut force_x = 0.0;

        if action_run != 0.0 {
            force_x += action_run * self.consts.move_force;
            if linvel.x * action_run < 0.0 {
                let dir = if linvel.x > 0.0 { -1.0 } else { 1.0 };
                force_x += dir * self.consts.braking_force;
            }
            force_x -= linvel.x * self.consts.linear_damping;
        } else {
            if linvel.x.abs() > 10.0 {
                let dir = if linvel.x > 0.0 { -1.0 } else { 1.0 };
                force_x += dir * self.consts.braking_force;
            } else {
                linvel.x = 0.0;
            }
        }

        linvel.x += force_x * dt;
        linvel.x = linvel.x.clamp(-self.consts.max_vx, self.consts.max_vx);

        // 3. Jump impulse
        let can_jump = is_on_ground || self.jump_tolerance_timer > 0.0;
        if action_jump && self.jump_cooldown_timer <= 0.0 && can_jump {
            linvel.y = self.consts.jump_impulse;
            self.jump_cooldown_timer = self.consts.jump_cooldown_max;
            self.jump_tolerance_timer = 0.0;
        }

        let old_vx = linvel.x;
        let old_x = player_pos.x;
        rb.set_linvel(linvel, true);

        // 4. Step Rapier Simulation
        let gravity = vector![0.0, self.consts.gravity];
        let integration_parameters = IntegrationParameters {
            dt,
            ..Default::default()
        };
        let physics_hooks = ();
        let event_handler = ();

        self.physics_pipeline.step(
            &gravity,
            &integration_parameters,
            &mut self.island_manager,
            &mut self.broad_phase,
            &mut self.narrow_phase,
            &mut self.rigid_body_set,
            &mut self.collider_set,
            &mut self.impulse_joint_set,
            &mut self.multibody_joint_set,
            &mut self.ccd_solver,
            Some(&mut self.query_pipeline),
            &physics_hooks,
            &event_handler,
        );

        // 5. Update self.delver from rigid body
        let rb = &mut self.rigid_body_set[self.player_body_handle];
        let pos = *rb.translation();
        let mut vel = *rb.linvel();

        // Check if we hit a wall horizontally (velocity was blocked/intended distance not travelled)
        let dx = (pos.x - old_x).abs();
        let intended_dx = (old_vx * dt).abs();
        if intended_dx > 0.1 && dx < 0.1 * intended_dx {
            vel.x = 0.0;
        } else if is_on_ground {
            // Preserve horizontal velocity to resolve corner normal forces and landing slowdowns
            vel.x = old_vx;
        }

        vel.x = vel.x.clamp(-self.consts.max_vx, self.consts.max_vx);
        vel.y = vel.y.clamp(-self.consts.max_vy, self.consts.max_vy);
        rb.set_linvel(vel, true);

        self.delver.x = pos.x;
        self.delver.y = pos.y;
        self.delver.vx = vel.x;
        self.delver.vy = vel.y;
        self.delver.is_on_ground = is_on_ground;

        // Check victory
        let half_w = self.consts.player_width / 2.0;
        let half_h = self.consts.player_height / 2.0;
        let left = self.delver.x - half_w;
        let right = self.delver.x + half_w;
        let bottom = self.delver.y - half_h;
        let top = self.delver.y + half_h;

        let (min_tx, max_tx, min_ty, max_ty) = self.grid.tile_coords_for_aabb(left, right, bottom, top);
        for ty in min_ty..=max_ty {
            for tx in min_tx..=max_tx {
                if self.grid.get(tx as i32, ty as i32) == 3 {
                    self.delver.is_victory = true;
                }
            }
        }

        // Out-of-bounds death
        if self.delver.y + half_h < 0.0 {
            self.delver.is_dead = true;
        }
    }
}
