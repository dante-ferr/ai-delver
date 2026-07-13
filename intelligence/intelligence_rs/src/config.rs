use anyhow::{Context, Result};
use serde::Deserialize;
use std::{fs, path::Path};

#[derive(Clone, Debug, Deserialize)]
#[serde(default)]
pub struct Config {
    pub learning_rate: f64,
    pub gamma: f32,
    pub entropy_regularization: f64,
    pub ppo_num_epochs: usize,
    pub clip_epsilon: f64,
    pub gae_lambda: f32,
    pub value_coefficient: f64,
    pub max_grad_norm: f64,
    pub minibatch_size: usize,
    pub env_batch_size: usize,
    pub device: String,
    pub not_finished_reward: f32,
    pub finished_reward: f32,
    pub turn_reward: f32,
    pub frame_step_reward: f32,
    pub tile_exploration_reward: f32,
    pub jump_reward: f32,
    pub wall_hugging_reward: f32,
    pub goal_distance_reward_scale: f32,
    pub actions_per_second: usize,
    pub max_seconds_per_episode: usize,
    pub checkpoint_interval: usize,
    pub seed: u64,
    pub no_learning: bool,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            learning_rate: 3e-4,
            gamma: 0.995,
            entropy_regularization: 0.01,
            ppo_num_epochs: 4,
            clip_epsilon: 0.2,
            gae_lambda: 0.95,
            value_coefficient: 0.5,
            max_grad_norm: 0.5,
            minibatch_size: 256,
            env_batch_size: 38,
            device: "cpu".into(),
            not_finished_reward: -10.0,
            finished_reward: 100.0,
            turn_reward: 0.0,
            frame_step_reward: -0.01,
            tile_exploration_reward: 0.04,
            jump_reward: -0.15,
            wall_hugging_reward: -0.2,
            goal_distance_reward_scale: 0.005,
            actions_per_second: 10,
            max_seconds_per_episode: 60,
            checkpoint_interval: 0,
            seed: 42,
            no_learning: false,
        }
    }
}

impl Config {
    pub fn load(path: &Path) -> Result<Self> {
        let text = fs::read_to_string(path)
            .with_context(|| format!("failed to read config {}", path.display()))?;
        toml::from_str(&text).context("invalid training config")
    }

    pub fn reward_scale(&self) -> f32 {
        [
            self.not_finished_reward,
            self.finished_reward,
            self.turn_reward,
            self.frame_step_reward,
            self.tile_exploration_reward,
            self.jump_reward,
            self.wall_hugging_reward,
            self.goal_distance_reward_scale,
        ]
        .into_iter()
        .map(f32::abs)
        .fold(0.0, f32::max)
        .max(1.0)
    }
}
