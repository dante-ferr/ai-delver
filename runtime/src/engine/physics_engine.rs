use std::collections::HashMap;
use std::fmt;

#[cfg(feature = "python")]
use pyo3::prelude::*;
use rapier2d::prelude::*;

use crate::engine::grid::TileGrid;
use crate::engine::physics_world::PhysicsWorld;
use crate::engine::world_config::WorldConfig;
use crate::world_objects::delver::{BaseDelver, DelverConfig};
use crate::world_objects::goal::BaseGoal;
use crate::world_objects::physics_entity::PhysicsEntity;

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum RuntimeError {
    EntityNotFound(String),
    DelverNotFound,
}

impl fmt::Display for RuntimeError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::EntityNotFound(id) => write!(formatter, "Entity with id {id} not found"),
            Self::DelverNotFound => formatter.write_str("Delver entity not found"),
        }
    }
}

impl std::error::Error for RuntimeError {}

pub type RuntimeResult<T> = Result<T, RuntimeError>;

#[cfg_attr(feature = "python", pyclass)]
pub struct RustPhysicsEngine {
    grid: TileGrid,
    entities: HashMap<String, PhysicsEntity>,
    goal: BaseGoal,
    world_config: WorldConfig,
    world: PhysicsWorld,
}

impl RustPhysicsEngine {
    /// Constructs a simulation from tile geometry and a world-space delver start.
    pub fn new(
        width: usize,
        height: usize,
        solid_tiles: Vec<(usize, usize)>,
        goal_tiles: Vec<(usize, usize)>,
        start_x: f32,
        start_y: f32,
        tile_size: f32,
    ) -> Self {
        Self::from_geometry_ref(
            width,
            height,
            &solid_tiles,
            &goal_tiles,
            start_x,
            start_y,
            tile_size,
        )
    }

    /// Constructs a simulation without requiring callers to clone level geometry.
    pub fn from_geometry_ref(
        width: usize,
        height: usize,
        solid_tiles: &[(usize, usize)],
        goal_tiles: &[(usize, usize)],
        start_x: f32,
        start_y: f32,
        tile_size: f32,
    ) -> Self {
        let delver_config = DelverConfig::default();
        let world_config = WorldConfig::default();
        let mut grid = TileGrid::new(width, height, tile_size);
        let mut world = PhysicsWorld::new();

        // Create player body (Dynamic body with rotation locked and CCD enabled)
        let player_body = RigidBodyBuilder::dynamic()
            .translation(vector![start_x, start_y])
            .lock_rotations()
            .additional_mass(delver_config.mass)
            .ccd_enabled(true)
            .build();
        let player_body_handle = world.rigid_bodies.insert(player_body);

        let half_w = delver_config.player_width / 2.0;
        let half_h = delver_config.player_height / 2.0;
        let border_radius = delver_config.border_radius;
        let player_collider = ColliderBuilder::round_cuboid(
            half_w - border_radius,
            half_h - border_radius,
            border_radius,
        )
        .density(delver_config.collider_density)
        .friction(delver_config.collider_friction)
        .restitution(delver_config.collider_restitution)
        .build();
        world.colliders.insert_with_parent(
            player_collider,
            player_body_handle,
            &mut world.rigid_bodies,
        );

        // Add static colliders for solid tiles by merging contiguous segments in each row
        let half_tile = tile_size / 2.0;
        let mut rows: std::collections::HashMap<i32, Vec<i32>> = std::collections::HashMap::new();
        for &(x, y) in solid_tiles {
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
                    .friction(world_config.tile_friction)
                    .restitution(world_config.tile_restitution)
                    .build();
                world.colliders.insert(tile_collider);

                i += 1;
            }
        }

        let mut goal_x = 0.0;
        let mut goal_y = 0.0;
        if !goal_tiles.is_empty() {
            let mut min_x = usize::MAX;
            let mut max_x = 0usize;
            let mut min_y = usize::MAX;
            let mut max_y = 0usize;
            for &(x, y) in goal_tiles {
                grid.set(x, y, 3);
                min_x = min_x.min(x);
                max_x = max_x.max(x);
                min_y = min_y.min(y);
                max_y = max_y.max(y);
            }
            // Sprite / BaseGoal sit at the geometric center of the full footprint
            // (physics space). Python Goal rendering adds +tile_size on Y to match
            // pytiling tile sprites.
            goal_x = (min_x as f32 + max_x as f32 + 1.0) * 0.5 * tile_size;
            goal_y = (height as f32 - (min_y as f32 + max_y as f32 + 1.0) * 0.5) * tile_size;
        }

        let mut entities = HashMap::new();
        let mut delver = BaseDelver::new("delver".to_string(), start_x, start_y, delver_config);
        delver.body_handle = player_body_handle;
        entities.insert("delver".to_string(), PhysicsEntity::Delver(delver));

        RustPhysicsEngine {
            grid,
            entities,
            goal: BaseGoal::new(goal_x, goal_y),
            world_config,
            world,
        }
    }

    /// An explicit geometry constructor for callers that prefer a descriptive name.
    pub fn from_geometry(
        width: usize,
        height: usize,
        solid_tiles: Vec<(usize, usize)>,
        goal_tiles: Vec<(usize, usize)>,
        start_x: f32,
        start_y: f32,
        tile_size: f32,
    ) -> Self {
        Self::new(
            width,
            height,
            solid_tiles,
            goal_tiles,
            start_x,
            start_y,
            tile_size,
        )
    }

    /// Advances the simulation using the same fixed-size substeps as Python.
    pub fn step_native(&mut self, dt: f32) -> RuntimeResult<BaseDelver> {
        let is_delver_dead = if let Some(PhysicsEntity::Delver(ref d)) = self.entities.get("delver")
        {
            d.is_dead
        } else {
            false
        };

        if is_delver_dead {
            return self.get_delver_native();
        }

        let sub_dt = 1.0 / self.world_config.physics_fps;
        let mut elapsed = 0.0;
        while elapsed < dt {
            let tick_dt = (dt - elapsed).min(sub_dt);
            self.tick_physics(tick_dt);
            elapsed += tick_dt;
        }

        self.get_delver_native()
    }

    pub fn set_entity_actions_native(
        &mut self,
        id: &str,
        action_run: f32,
        action_jump: bool,
    ) -> RuntimeResult<()> {
        if let Some(entity) = self.entities.get_mut(id) {
            match entity {
                PhysicsEntity::Delver(delver) => {
                    delver.action_run = action_run;
                    delver.action_jump = action_jump;
                }
            }
            Ok(())
        } else {
            Err(RuntimeError::EntityNotFound(id.to_owned()))
        }
    }

    pub fn set_delver_action(&mut self, action_run: f32, action_jump: bool) -> RuntimeResult<()> {
        self.set_entity_actions_native("delver", action_run, action_jump)
    }

    pub fn delver(&self) -> RuntimeResult<&BaseDelver> {
        if let Some(PhysicsEntity::Delver(ref delver)) = self.entities.get("delver") {
            Ok(delver)
        } else {
            Err(RuntimeError::DelverNotFound)
        }
    }

    pub fn get_delver_native(&self) -> RuntimeResult<BaseDelver> {
        self.delver().cloned()
    }

    pub fn goal(&self) -> &BaseGoal {
        &self.goal
    }

    pub fn get_goal_native(&self) -> BaseGoal {
        self.goal.clone()
    }

    pub fn goal_position(&self) -> (f32, f32) {
        (self.goal.x, self.goal.y)
    }

    pub fn max_velocity(&self) -> (f32, f32) {
        match self.entities.get("delver") {
            Some(PhysicsEntity::Delver(delver)) => (delver.config.max_vx, delver.config.max_vy),
            None => {
                let config = DelverConfig::default();
                (config.max_vx, config.max_vy)
            }
        }
    }

    pub fn get_entity_rotation_native(&self, id: &str) -> RuntimeResult<f32> {
        if let Some(entity) = self.entities.get(id) {
            let rb = &self.world.rigid_bodies[entity.body_handle()];
            Ok(rb.rotation().angle())
        } else {
            Err(RuntimeError::EntityNotFound(id.to_owned()))
        }
    }

    pub fn local_view(&self, id: &str, radius: i32) -> RuntimeResult<Vec<i32>> {
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
            Err(RuntimeError::EntityNotFound(id.to_owned()))
        }
    }
}

#[cfg(feature = "python")]
fn runtime_error_to_py(error: RuntimeError) -> pyo3::PyErr {
    pyo3::exceptions::PyKeyError::new_err(error.to_string())
}

#[cfg(feature = "python")]
#[pyo3::pymethods]
impl RustPhysicsEngine {
    #[new]
    fn py_new(
        width: usize,
        height: usize,
        solid_tiles: Vec<(usize, usize)>,
        goal_tiles: Vec<(usize, usize)>,
        start_x: f32,
        start_y: f32,
        tile_size: f32,
    ) -> Self {
        Self::new(
            width,
            height,
            solid_tiles,
            goal_tiles,
            start_x,
            start_y,
            tile_size,
        )
    }

    #[pyo3(name = "step")]
    fn step_py(&mut self, py: pyo3::Python<'_>, dt: f32) -> pyo3::PyResult<BaseDelver> {
        py.allow_threads(|| self.step_native(dt))
            .map_err(runtime_error_to_py)
    }

    #[pyo3(name = "set_entity_actions")]
    fn set_entity_actions_py(
        &mut self,
        id: &str,
        action_run: f32,
        action_jump: bool,
    ) -> pyo3::PyResult<()> {
        self.set_entity_actions_native(id, action_run, action_jump)
            .map_err(runtime_error_to_py)
    }

    #[pyo3(name = "get_delver")]
    fn get_delver_py(&self) -> pyo3::PyResult<BaseDelver> {
        self.get_delver_native().map_err(runtime_error_to_py)
    }

    #[pyo3(name = "get_goal")]
    fn get_goal_py(&self) -> BaseGoal {
        self.get_goal_native()
    }

    #[pyo3(name = "get_goal_position")]
    fn get_goal_position_py(&self) -> (f32, f32) {
        self.goal_position()
    }

    #[pyo3(name = "get_entity_rotation")]
    fn get_entity_rotation_py(&self, id: &str) -> pyo3::PyResult<f32> {
        self.get_entity_rotation_native(id)
            .map_err(runtime_error_to_py)
    }

    #[pyo3(name = "get_local_view")]
    fn get_local_view_py(&self, id: &str, radius: i32) -> pyo3::PyResult<Vec<i32>> {
        self.local_view(id, radius).map_err(runtime_error_to_py)
    }
}

impl RustPhysicsEngine {
    fn tick_physics(&mut self, dt: f32) {
        self.world
            .query_pipeline
            .update(&self.world.rigid_bodies, &self.world.colliders);

        // 1. Delegate pre-step updates to all dynamic entities
        let entity_ids: Vec<String> = self.entities.keys().cloned().collect();
        for id in &entity_ids {
            let entity = self.entities.get_mut(id).unwrap();
            entity.pre_step(dt, &mut self.world);
        }

        // 2. Step the Physics World simulation
        let gravity = vector![0.0, self.world_config.gravity];
        self.world.step(&gravity, dt, &self.world_config);

        // Update query pipeline after step so post-step raycasts query the new positions
        self.world
            .query_pipeline
            .update(&self.world.rigid_bodies, &self.world.colliders);

        // 3. Delegate post-step updates
        for id in &entity_ids {
            let entity = self.entities.get_mut(id).unwrap();
            entity.post_step(&mut self.world, &self.grid);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn native_api_constructs_without_python() {
        let solids = [(0, 4), (1, 4), (2, 4), (3, 4), (4, 4)];
        let goals = [(3, 3)];
        let mut engine =
            RustPhysicsEngine::from_geometry_ref(5, 5, &solids, &goals, 24.0, 40.0, 16.0);

        engine.set_delver_action(1.0, false).unwrap();
        assert_eq!(engine.goal_position(), (56.0, 24.0));
        assert_eq!(engine.local_view("delver", 7).unwrap().len(), 225);
        assert_eq!(engine.max_velocity(), (500.0, 1000.0));
    }

    #[test]
    fn goal_sprite_uses_footprint_center() {
        // Bottom-left (2, 3), size 2x2 → cells (2,2),(3,2),(2,3),(3,3)
        let goals = [(2, 2), (3, 2), (2, 3), (3, 3)];
        let engine =
            RustPhysicsEngine::from_geometry_ref(6, 5, &[], &goals, 24.0, 40.0, 16.0);
        // Footprint center: x midpoint of tiles 2..3 → 48; y midpoint → 32
        assert_eq!(engine.goal_position(), (48.0, 32.0));
    }

    /// Empirical jump envelope vs tile surfaces (y-up world, row 0 = top of grid).
    ///
    /// Tuned for reliable +4 surface rise (~64px) with apex ~70px (~4.4 tiles) so
    /// wall-kiss landings are not subframe-fragile. A +5 rise (80px) stays unreachable.
    #[test]
    fn measures_jump_apex_and_ledge_landing() {
        let tile = 16.0_f32;
        let width = 16_usize;
        let height = 14_usize;
        let floor_row = height - 1; // bottom row
        let half_h = DelverConfig::default().player_height / 2.0;
        let half_w = DelverConfig::default().player_width / 2.0;

        // Continuous floor on the bottom row.
        let mut solids: Vec<(usize, usize)> = (0..width).map(|x| (x, floor_row)).collect();
        // Floating +4 ledge (row delta 4) — wide enough to stand on after a wall-kiss.
        let ledge4 = floor_row - 4;
        for x in 6..10 {
            solids.push((x, ledge4));
        }
        // Floating +5 ledge further right (should remain unreachable).
        let ledge5 = floor_row - 5;
        for x in 12..15 {
            solids.push((x, ledge5));
        }

        let floor_top = (height - floor_row) as f32 * tile; // == tile
        let ledge4_top = (height - ledge4) as f32 * tile;
        let ledge5_top = (height - ledge5) as f32 * tile;
        // Start kissing the left face of the +4 ledge (wall-kiss takeoff).
        let ledge4_left = 6.0 * tile;
        let start_x = ledge4_left - half_w - 0.5;
        let start_y = floor_top + half_h + 1.0;

        let mut engine = RustPhysicsEngine::from_geometry_ref(
            width,
            height,
            &solids,
            &[],
            start_x,
            start_y,
            tile,
        );

        // Settle onto the floor.
        engine.set_delver_action(0.0, false).unwrap();
        for _ in 0..120 {
            let _ = engine.step_native(1.0 / 60.0).unwrap();
        }
        let grounded = engine.delver().unwrap();
        let stand_y = grounded.y;
        let stand_feet = stand_y - half_h;
        assert!(
            grounded.is_on_ground,
            "expected to be grounded after settle; feet={stand_feet}, floor_top={floor_top}"
        );

        // Jump while holding run into the ledge face (wall-kiss ascent).
        engine.set_delver_action(1.0, true).unwrap();
        let mut max_y = stand_y;
        let mut max_feet = stand_feet;
        let mut landed_on_4 = false;
        let mut landed_on_5 = false;

        for i in 0..300 {
            if i == 4 {
                // Release jump after takeoff; keep pressing into the ledge.
                engine.set_delver_action(1.0, false).unwrap();
            }
            let d = engine.step_native(1.0 / 60.0).unwrap();
            max_y = max_y.max(d.y);
            max_feet = max_feet.max(d.y - half_h);
            if d.is_on_ground {
                let feet = d.y - half_h;
                if d.x >= 6.0 * tile && d.x < 10.0 * tile && (feet - ledge4_top).abs() < 4.0 {
                    landed_on_4 = true;
                }
                if d.x >= 12.0 * tile && d.x < 15.0 * tile && (feet - ledge5_top).abs() < 4.0 {
                    landed_on_5 = true;
                }
            }
        }

        let rise_px = max_y - stand_y;
        let rise_tiles = rise_px / tile;
        let feet_rise_px = max_feet - stand_feet;
        eprintln!(
            "jump_measure stand_y={stand_y:.3} stand_feet={stand_feet:.3} floor_top={floor_top:.3}"
        );
        eprintln!(
            "jump_measure max_y={max_y:.3} rise_px={rise_px:.3} rise_tiles={rise_tiles:.3}"
        );
        eprintln!(
            "jump_measure max_feet={max_feet:.3} feet_rise_px={feet_rise_px:.3} feet_rise_tiles={}",
            feet_rise_px / tile
        );
        eprintln!(
            "jump_measure ledge4_top={ledge4_top:.3} ledge5_top={ledge5_top:.3} landed4={landed_on_4} landed5={landed_on_5}"
        );

        // Ballistic target ~70px / 4.375 tiles; Rapier should land in a tight band.
        // Contact with the ledge face can shave a little off free-apex, so allow a wider floor.
        assert!(
            (4.2..=4.5).contains(&rise_tiles),
            "expected ~4.2–4.5 tile COM rise, got {rise_tiles}"
        );
        assert!(
            landed_on_4,
            "must land on +4 via wall-kiss approach; feet apex was {max_feet}, ledge4_top={ledge4_top}"
        );
        assert!(
            !landed_on_5,
            "must not land on a +5 surface rise (80px); feet apex was {max_feet}"
        );
    }
}
