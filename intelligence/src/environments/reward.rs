use crate::config::Config;
use ai_delver_level::Level;
use std::collections::VecDeque;

#[derive(Clone)]
pub struct DijkstraGrid {
    width: usize,
    height: usize,
    distances: Vec<i32>,
}

impl DijkstraGrid {
    pub fn new(level: &Level) -> Self {
        let mut distances = vec![-1; level.width * level.height];
        let mut blocked = vec![false; level.width * level.height];
        for &(x, y) in &level.solid_tiles {
            blocked[y * level.width + x] = true;
        }
        let goal_tiles = level.goal_tiles();
        let mut queue = VecDeque::from(goal_tiles.clone());
        for &(gx, gy) in &goal_tiles {
            distances[gy * level.width + gx] = 0;
        }
        while let Some((x, y)) = queue.pop_front() {
            let distance = distances[y * level.width + x] + 1;
            for (nx, ny) in [
                (x.wrapping_sub(1), y),
                (x + 1, y),
                (x, y.wrapping_sub(1)),
                (x, y + 1),
            ] {
                if nx >= level.width
                    || ny >= level.height
                    || distances[ny * level.width + nx] >= 0
                    || blocked[ny * level.width + nx]
                {
                    continue;
                }
                distances[ny * level.width + nx] = distance;
                queue.push_back((nx, ny));
            }
        }
        Self {
            width: level.width,
            height: level.height,
            distances,
        }
    }

    pub fn distance(&self, x: i32, y: i32) -> f32 {
        if x < 0 || y < 0 || x >= self.width as i32 || y >= self.height as i32 {
            -1.0
        } else {
            self.distances[y as usize * self.width + x as usize] as f32
        }
    }
}

pub struct RewardState {
    pub dijkstra: DijkstraGrid,
    pub last_distance: f32,
    pub last_x: f32,
    pub wall_stuck_frames: usize,
}

pub struct RewardInput {
    pub reached_goal: bool,
    pub timed_out: bool,
    pub run: i64,
    /// True only on the env step where a jump takeoff impulse occurs (not while held in air).
    pub jump_takeoff: bool,
    pub previous_run: Option<i64>,
    pub x: f32,
    pub grounded: bool,
    /// Number of exploration cells newly marked this step (air + floor).
    pub tiles_explored: usize,
    pub distance: f32,
}

impl RewardState {
    pub fn new(level: &Level) -> Self {
        let dijkstra = DijkstraGrid::new(level);
        let distance = dijkstra.distance(level.delver.0 as i32, level.delver.1 as i32);
        let x = level.tile_center(level.delver).0;
        Self {
            dijkstra,
            last_distance: distance,
            last_x: x,
            wall_stuck_frames: 0,
        }
    }

    pub fn calculate(&mut self, input: RewardInput, config: &Config) -> f32 {
        let mut reward = if input.reached_goal {
            config.finished_reward
        } else if input.timed_out {
            config.not_finished_reward
        } else {
            0.0
        };
        if input
            .previous_run
            .is_some_and(|last| last != 0 && input.run != 0 && last != input.run)
        {
            reward += config.turn_reward;
        }
        if input.jump_takeoff {
            reward += config.jump_reward;
        }
        reward += config.frame_step_reward;
        if input.tiles_explored > 0 {
            reward += config.tile_exploration_reward * input.tiles_explored as f32;
        }
        if input.distance >= 0.0 && self.last_distance >= 0.0 {
            reward += (self.last_distance - input.distance) * config.goal_distance_reward_scale;
        }
        if input.distance >= 0.0 {
            self.last_distance = input.distance;
        }
        if input.run != 0 && (input.x - self.last_x).abs() < 0.001 && input.grounded {
            self.wall_stuck_frames += 1;
            if self.wall_stuck_frames > 10 {
                reward += config.wall_hugging_reward;
            }
        } else {
            self.wall_stuck_frames = 0;
        }
        self.last_x = input.x;
        reward / config.reward_scale()
    }
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
                  {"name": "Delver", "position": [1, 1], "size": [1, 3]},
                  {"name": "Goal", "position": [6, 1], "size": [1, 1]}
                ]}] }
              }
            }"#,
        )
        .expect("test level")
    }

    #[test]
    fn reward_scale_includes_wall_hugging() {
        let mut config = Config::default();
        config.finished_reward = 0.0;
        config.not_finished_reward = 0.0;
        config.wall_hugging_reward = -12.0;
        assert_eq!(config.reward_scale(), 12.0);
    }

    #[test]
    fn exploration_pays_per_tile_and_jump_only_on_takeoff() {
        let mut config = Config::default();
        config.finished_reward = 0.0;
        config.not_finished_reward = 0.0;
        config.turn_reward = 0.0;
        config.frame_step_reward = 0.0;
        config.wall_hugging_reward = 0.0;
        config.goal_distance_reward_scale = 0.0;
        config.tile_exploration_reward = 0.1;
        config.jump_reward = -0.5;

        let mut state = RewardState::new(&test_level());
        let base = RewardInput {
            reached_goal: false,
            timed_out: false,
            run: 1,
            jump_takeoff: false,
            previous_run: Some(1),
            x: 0.0,
            grounded: true,
            tiles_explored: 0,
            distance: -1.0,
        };

        let explore_only = state.calculate(
            RewardInput {
                tiles_explored: 3,
                ..base
            },
            &config,
        );
        let scale = config.reward_scale();
        assert!((explore_only - 0.3 / scale).abs() < 1e-5);

        let jump_only = state.calculate(
            RewardInput {
                jump_takeoff: true,
                tiles_explored: 0,
                ..base
            },
            &config,
        );
        assert!((jump_only - (-0.5) / scale).abs() < 1e-5);

        let held_jump_no_takeoff = state.calculate(
            RewardInput {
                jump_takeoff: false,
                tiles_explored: 0,
                grounded: false,
                ..base
            },
            &config,
        );
        assert!((held_jump_no_takeoff - 0.0).abs() < 1e-5);
    }
}
