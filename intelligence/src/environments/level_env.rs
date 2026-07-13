use super::{
    exploration::ExplorationGrid,
    reward::{RewardInput, RewardState},
};
use crate::config::Config;
use ai_delver_level::{Level, DEFAULT_TILE_SIZE, MAX_GRID_SIZE};
use runtime_core::RustPhysicsEngine;
use std::sync::Arc;

#[derive(Clone)]
pub struct Observation {
    pub local_view: [f32; 225],
    pub global_state: [f32; 7],
}

pub struct Step {
    pub observation: Observation,
    pub reward: f32,
    pub done: bool,
    pub victory: bool,
}

pub struct LevelEnvironment {
    level: Arc<Level>,
    config: Arc<Config>,
    physics: RustPhysicsEngine,
    exploration: ExplorationGrid,
    rewards: RewardState,
    frame: usize,
    previous_run: Option<i64>,
}

impl LevelEnvironment {
    pub fn new(level: Arc<Level>, config: Arc<Config>) -> Self {
        let physics = create_physics(&level);
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
        }
    }

    pub fn reset(&mut self) -> Observation {
        self.physics = create_physics(&self.level);
        self.exploration = ExplorationGrid::new(self.level.width, self.level.height);
        self.rewards = RewardState::new(&self.level);
        self.frame = 0;
        self.previous_run = None;
        self.observation()
    }

    pub fn step(&mut self, run_action: i64, jump_action: i64) -> Step {
        let run = run_action - 1;
        let jump = jump_action != 0;
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
        let (tx, ty) = self.grid_position(x, y);
        let newly_explored = self.exploration.step_on(tx, ty, 1);
        let distance = self.rewards.dijkstra.distance(tx, ty);
        let reward = self.rewards.calculate(
            RewardInput {
                reached_goal: delver.is_victory,
                timed_out: timed_out || delver.is_dead,
                run,
                jump,
                previous_run: self.previous_run,
                x,
                grounded: delver.is_on_ground,
                newly_explored,
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
        let local_view: [f32; 225] = self
            .physics
            .local_view("delver", 7)
            .expect("physics engine always contains the delver")
            .into_iter()
            .map(|cell| cell as f32)
            .collect::<Vec<_>>()
            .try_into()
            .expect("radius 7 always produces a 15x15 view");
        Observation {
            local_view,
            global_state: [
                (gx - x) / goal_distance_norm,
                (gy - y) / goal_distance_norm,
                vx / max_vx,
                vy / max_vy,
                x.rem_euclid(self.level.tile_size) / self.level.tile_size,
                y.rem_euclid(self.level.tile_size) / self.level.tile_size,
                delver.is_on_ground as u8 as f32,
            ],
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

fn create_physics(level: &Level) -> RustPhysicsEngine {
    let (start_x, start_y) = level.tile_center(level.delver);
    RustPhysicsEngine::from_geometry_ref(
        level.width,
        level.height,
        &level.solid_tiles,
        &[level.goal],
        start_x,
        start_y,
        level.tile_size,
    )
}
