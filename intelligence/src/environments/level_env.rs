use super::{
    exploration::ExplorationGrid,
    observation::{GLOBAL_STATE_SIZE, LOCAL_VIEW_CELLS, LOCAL_VIEW_RADIUS, LOCAL_VIEW_SIDE},
    reward::{RewardInput, RewardState},
};
use crate::config::Config;
use ai_delver_level::{Level, DEFAULT_TILE_SIZE, MAX_GRID_SIZE};
use rand::Rng;
use runtime_core::RustPhysicsEngine;
use std::sync::Arc;

#[derive(Clone)]
pub struct Observation {
    pub local_view: [f32; LOCAL_VIEW_CELLS],
    pub global_state: [f32; GLOBAL_STATE_SIZE],
}

pub struct Step {
    pub observation: Observation,
    pub reward: f32,
    pub done: bool,
    pub victory: bool,
    /// True when a jump takeoff impulse occurred this step (not held-air frames).
    pub jump_takeoff: bool,
}

#[derive(Clone, Copy, Debug)]
pub struct DelverPose {
    pub x: f32,
    pub y: f32,
    pub vx: f32,
    pub vy: f32,
    pub is_on_ground: bool,
    pub action_run: f32,
    pub action_jump: bool,
}

pub struct LevelEnvironment {
    level: Arc<Level>,
    config: Arc<Config>,
    physics: RustPhysicsEngine,
    exploration: ExplorationGrid,
    rewards: RewardState,
    frame: usize,
    previous_run: Option<i64>,
    augmentations_enabled: bool,
    is_mirrored: bool,
    spawn_jitter_x: f32,
    spawn_jitter_y: f32,
    goal_jitter_x: f32,
    goal_jitter_y: f32,
    dropout_mask: [bool; LOCAL_VIEW_CELLS],
}

impl LevelEnvironment {
    pub fn new(level: Arc<Level>, config: Arc<Config>) -> Self {
        let physics = create_physics(&level, (0.0, 0.0));
        let exploration = ExplorationGrid::new(level.width, level.height);
        let rewards = RewardState::new(&level);
        Self {
            level,
            config,
            physics,
            exploration,
            rewards,
            frame: 0,
            previous_run: None,
            augmentations_enabled: true,
            is_mirrored: false,
            spawn_jitter_x: 0.0,
            spawn_jitter_y: 0.0,
            goal_jitter_x: 0.0,
            goal_jitter_y: 0.0,
            dropout_mask: [false; LOCAL_VIEW_CELLS],
        }
    }

    pub fn set_augmentations_enabled(&mut self, enabled: bool) {
        self.augmentations_enabled = enabled;
        if !enabled {
            self.is_mirrored = false;
            self.spawn_jitter_x = 0.0;
            self.spawn_jitter_y = 0.0;
            self.goal_jitter_x = 0.0;
            self.goal_jitter_y = 0.0;
            self.dropout_mask = [false; LOCAL_VIEW_CELLS];
        }
    }

    #[cfg(test)]
    pub fn is_mirrored(&self) -> bool {
        self.is_mirrored
    }

    pub fn reset(&mut self) -> Observation {
        let mut rng = rand::rng();
        if self.augmentations_enabled && self.config.enable_augmentations {
            self.is_mirrored = rng.random::<f32>() < self.config.mirror_augmentation_prob;

            if self.config.spawn_jitter_px > 0.0 {
                self.spawn_jitter_x =
                    (rng.random::<f32>() * 2.0 - 1.0) * self.config.spawn_jitter_px;
                self.spawn_jitter_y =
                    (rng.random::<f32>() * 2.0 - 1.0) * self.config.spawn_jitter_px;
            } else {
                self.spawn_jitter_x = 0.0;
                self.spawn_jitter_y = 0.0;
            }

            if self.config.goal_jitter_norm > 0.0 {
                self.goal_jitter_x =
                    (rng.random::<f32>() * 2.0 - 1.0) * self.config.goal_jitter_norm;
                self.goal_jitter_y =
                    (rng.random::<f32>() * 2.0 - 1.0) * self.config.goal_jitter_norm;
            } else {
                self.goal_jitter_x = 0.0;
                self.goal_jitter_y = 0.0;
            }

            if self.config.local_view_dropout_prob > 0.0 {
                for cell in self.dropout_mask.iter_mut() {
                    *cell = rng.random::<f32>() < self.config.local_view_dropout_prob;
                }
            } else {
                self.dropout_mask = [false; LOCAL_VIEW_CELLS];
            }
        } else {
            self.is_mirrored = false;
            self.spawn_jitter_x = 0.0;
            self.spawn_jitter_y = 0.0;
            self.goal_jitter_x = 0.0;
            self.goal_jitter_y = 0.0;
            self.dropout_mask = [false; LOCAL_VIEW_CELLS];
        }

        self.physics = create_physics(&self.level, (self.spawn_jitter_x, self.spawn_jitter_y));
        self.exploration = ExplorationGrid::new(self.level.width, self.level.height);
        self.rewards = RewardState::new(&self.level);
        self.frame = 0;
        self.previous_run = None;
        self.observation()
    }

    pub fn step(&mut self, run_action: i64, jump_action: i64) -> Step {
        let effective_run_action = if self.is_mirrored {
            2 - run_action
        } else {
            run_action
        };
        let run = effective_run_action - 1;
        let jump = jump_action != 0;
        let before = self
            .physics
            .delver()
            .expect("physics engine always contains the delver");
        let vy_before = before.vy;
        self.physics
            .set_delver_action(run as f32, jump)
            .expect("physics engine always contains the delver");
        let delver = self
            .physics
            .step_native(1.0 / self.config.actions_per_second as f32)
            .expect("physics engine always contains the delver");
        self.frame += 1;
        let timed_out =
            self.frame >= self.config.max_seconds_per_episode * self.config.actions_per_second;
        let done = delver.is_victory || delver.is_dead || timed_out;
        let (x, y) = (delver.x, delver.y);
        let player_height = runtime_core::DelverConfig::default().player_height;
        let jump_impulse = runtime_core::DelverConfig::default().jump_impulse;
        let half_h = player_height / 2.0;
        let (tx, ty) = self.grid_position(x, y);
        let feet_ty = self.grid_position(x, y - half_h).1;
        let head_ty = self.grid_position(x, y + half_h).1;
        let tiles_explored = self
            .exploration
            .step_on_vertical_span(tx, feet_ty, head_ty, 1);
        let jump_takeoff = jump && delver.vy > vy_before + jump_impulse * 0.25;
        let distance = self.rewards.dijkstra.distance(tx, ty);
        let reward = self.rewards.calculate(
            RewardInput {
                reached_goal: delver.is_victory,
                timed_out: timed_out || delver.is_dead,
                run,
                jump_takeoff,
                previous_run: self.previous_run,
                x,
                grounded: delver.is_on_ground,
                tiles_explored,
                distance,
            },
            &self.config,
        );
        self.previous_run = Some(run);
        Step {
            observation: self.observation(),
            reward,
            done,
            victory: delver.is_victory,
            jump_takeoff,
        }
    }

    pub fn observation(&self) -> Observation {
        let delver = self
            .physics
            .delver()
            .expect("physics engine always contains the delver");
        let (x, y, vx, vy) = (delver.x, delver.y, delver.vx, delver.vy);
        let (gx, gy) = self.physics.goal_position();
        let (max_vx, max_vy) = self.physics.max_velocity();
        let goal_distance_norm = MAX_GRID_SIZE as f32 * DEFAULT_TILE_SIZE;
        let mut local_view_vec: Vec<f32> = self
            .physics
            .local_view("delver", LOCAL_VIEW_RADIUS)
            .expect("physics engine always contains the delver")
            .into_iter()
            .map(|cell| cell as f32)
            .collect();

        // Apply local_view tile dropout if mask is active
        if self.augmentations_enabled && self.config.enable_augmentations {
            for (idx, &masked) in self.dropout_mask.iter().enumerate() {
                if masked && idx < local_view_vec.len() {
                    local_view_vec[idx] = 0.0;
                }
            }
        }

        // Apply horizontal matrix flip if mirrored
        if self.is_mirrored {
            let side = LOCAL_VIEW_SIDE; // 25
            let mut flipped = vec![0.0; LOCAL_VIEW_CELLS];
            for r in 0..side {
                for c in 0..side {
                    let src_idx = r * side + c;
                    let dst_idx = r * side + (side - 1 - c);
                    flipped[dst_idx] = local_view_vec[src_idx];
                }
            }
            local_view_vec = flipped;
        }

        let local_view: [f32; LOCAL_VIEW_CELLS] = local_view_vec
            .try_into()
            .expect("LOCAL_VIEW_RADIUS always produces LOCAL_VIEW_CELLS cells");

        let raw_dx = (gx - x) / goal_distance_norm + self.goal_jitter_x;
        let raw_dy = (gy - y) / goal_distance_norm + self.goal_jitter_y;
        let raw_vx = vx / max_vx;
        let raw_vy = vy / max_vy;

        let final_dx = if self.is_mirrored { -raw_dx } else { raw_dx };
        let final_vx = if self.is_mirrored { -raw_vx } else { raw_vx };

        Observation {
            local_view,
            global_state: [
                final_dx,
                raw_dy,
                final_vx,
                raw_vy,
                x.rem_euclid(self.level.tile_size) / self.level.tile_size,
                y.rem_euclid(self.level.tile_size) / self.level.tile_size,
                delver.is_on_ground as u8 as f32,
            ],
        }
    }

    /// Pose used for showcase `frame_snapshots` (state-sync replay + path visualizer).
    pub fn delver_pose(&self) -> DelverPose {
        let delver = self
            .physics
            .delver()
            .expect("physics engine always contains the delver");
        DelverPose {
            x: delver.x,
            y: delver.y,
            vx: delver.vx,
            vy: delver.vy,
            is_on_ground: delver.is_on_ground,
            action_run: delver.action_run,
            action_jump: delver.action_jump,
        }
    }

    fn grid_position(&self, x: f32, y: f32) -> (i32, i32) {
        (
            (x / self.level.tile_size).floor() as i32,
            ((self.level.height as f32 * self.level.tile_size - y) / self.level.tile_size).floor()
                as i32,
        )
    }
}

fn create_physics(level: &Level, spawn_offset: (f32, f32)) -> RustPhysicsEngine {
    let player_height = runtime_core::DelverConfig::default().player_height;
    let (start_x, start_y) = level.delver_spawn_center(player_height);
    let goal_tiles = level.goal_tiles();
    RustPhysicsEngine::from_geometry_ref(
        level.width,
        level.height,
        &level.solid_tiles,
        &goal_tiles,
        start_x + spawn_offset.0,
        start_y + spawn_offset.1,
        level.tile_size,
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_level() -> Level {
        Level::from_json(
            r#"{
              "_name": "t",
              "map": {
                "grid_size": [8, 8],
                "tile_size": [16.0, 16.0],
                "tilemap": { "layers": [{ "elements": [
                  {"name": "Terrain", "position": [0, 0], "size": [8, 1]}
                ]}] },
                "world_objects_map": { "layers": [{ "elements": [
                  {"name": "delver", "position": [1, 5], "size": [1, 3]},
                  {"name": "goal", "position": [6, 5], "size": [1, 1]}
                ]}] }
              }
            }"#,
        )
        .expect("test level")
    }

    #[test]
    fn test_mirroring_matrix_flip() {
        let side = LOCAL_VIEW_SIDE;
        let mut original = vec![0.0_f32; LOCAL_VIEW_CELLS];
        // Set column 0 to 1.0
        for r in 0..side {
            original[r * side + 0] = 1.0;
        }

        let mut flipped = vec![0.0_f32; LOCAL_VIEW_CELLS];
        for r in 0..side {
            for c in 0..side {
                let src_idx = r * side + c;
                let dst_idx = r * side + (side - 1 - c);
                flipped[dst_idx] = original[src_idx];
            }
        }

        // Flipped column 0 should now be column 24
        for r in 0..side {
            assert_eq!(flipped[r * side + 24], 1.0);
            assert_eq!(flipped[r * side + 0], 0.0);
        }
    }

    #[test]
    fn test_action_remapping() {
        let remap = |run_action: i64, is_mirrored: bool| -> i64 {
            if is_mirrored {
                2 - run_action
            } else {
                run_action
            }
        };

        // Standard
        assert_eq!(remap(0, false), 0); // Left stays Left
        assert_eq!(remap(1, false), 1); // Idle stays Idle
        assert_eq!(remap(2, false), 2); // Right stays Right

        // Mirrored
        assert_eq!(remap(0, true), 2); // Left becomes Right
        assert_eq!(remap(1, true), 1); // Idle stays Idle
        assert_eq!(remap(2, true), 0); // Right becomes Left
    }

    #[test]
    fn test_set_augmentations_disabled() {
        let level = Arc::new(test_level());
        let config = Arc::new(Config::default());
        let mut env = LevelEnvironment::new(level, config);
        env.set_augmentations_enabled(false);
        assert!(!env.augmentations_enabled);
        assert!(!env.is_mirrored());
    }
}

