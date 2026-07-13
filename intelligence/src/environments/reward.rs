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
        let mut queue = VecDeque::from([(level.goal.0, level.goal.1)]);
        distances[level.goal.1 * level.width + level.goal.0] = 0;
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
}

pub struct RewardInput {
    pub reached_goal: bool,
    pub timed_out: bool,
    pub run: i64,
    pub jump: bool,
    pub previous_run: Option<i64>,
    pub x: f32,
    pub grounded: bool,
    pub newly_explored: bool,
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
        if input.jump {
            reward += config.jump_reward;
        }
        reward += config.frame_step_reward;
        if input.newly_explored {
            reward += config.tile_exploration_reward;
        }
        if input.distance >= 0.0 && self.last_distance >= 0.0 {
            reward += (self.last_distance - input.distance) * config.goal_distance_reward_scale;
        }
        if input.distance >= 0.0 {
            self.last_distance = input.distance;
        }
        if input.run != 0 && (input.x - self.last_x).abs() < 0.001 && input.grounded {
            reward += config.wall_hugging_reward;
        }
        self.last_x = input.x;
        reward / config.reward_scale()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reward_scale_includes_wall_hugging() {
        let mut config = Config::default();
        config.finished_reward = 0.0;
        config.not_finished_reward = 0.0;
        config.wall_hugging_reward = -12.0;
        assert_eq!(config.reward_scale(), 12.0);
    }
}
