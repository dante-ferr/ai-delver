use anyhow::{Context, Result};
use serde::Deserialize;
use std::{fs, path::Path};

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Config {
    pub learning_rate: f64,
    pub gamma: f32,
    /// Discovery-band entropy (before first clear of the train session's levels).
    pub entropy_regularization: f64,
    /// Post-clear entropy target (lower → sharper argmax / faster neat lock).
    /// Anneals from `entropy_regularization` over `entropy_anneal_cycles`.
    pub entropy_regularization_polish: f64,
    /// Cycles after first clear to reach `entropy_regularization_polish`.
    pub entropy_anneal_cycles: usize,
    pub ppo_num_epochs: usize,
    pub clip_epsilon: f64,
    pub gae_lambda: f32,
    pub value_coefficient: f64,
    pub max_grad_norm: f64,
    pub minibatch_size: usize,
    pub env_batch_size: usize,
    pub device: String,
    /// Local-view encoder width (projects `LOCAL_VIEW_CELLS` → this dim).
    pub local_feature_dim: usize,
    /// LSTM input/hidden size after the fused MLP tower.
    pub lstm_hidden_size: usize,
    /// Hidden width of the fused MLP before the LSTM.
    pub mlp_hidden_dim: usize,
    pub not_finished_reward: f32,
    pub finished_reward: f32,
    pub turn_reward: f32,
    pub frame_step_reward: f32,
    pub tile_exploration_reward: f32,
    pub jump_reward: f32,
    /// Post-clear jump cost target (typically more negative than `jump_reward`).
    /// After a level's first victory, `jump_reward` anneals toward this over
    /// `jump_anneal_cycles`. Not applied to turn_reward (mazes need cheap turns).
    pub jump_reward_polish: f32,
    /// Cycles after first clear to fully reach `jump_reward_polish`.
    pub jump_anneal_cycles: usize,
    pub wall_hugging_reward: f32,
    pub goal_distance_reward_scale: f32,
    pub actions_per_second: usize,
    pub collect_seconds_per_env: usize,
    pub max_seconds_per_episode: usize,
    pub checkpoint_interval: usize,
    pub seed: u64,
    pub no_learning: bool,
    pub max_training_levels: usize,
    /// When true, cleanest victorious trajectories are rehearsed into PPO.
    pub goal_rehearsal_lock: bool,
    /// Behavioral-cloning epochs over each locked trajectory each cycle.
    pub goal_rehearsal_epochs: usize,
    /// Stochastic scout episodes per level per cycle (find cleaner wins than greedy).
    pub goal_rehearsal_scout_episodes: usize,
}

#[cfg(test)]
impl Default for Config {
    fn default() -> Self {
        Self {
            learning_rate: 3e-4,
            gamma: 0.995,
            entropy_regularization: 0.06,
            entropy_regularization_polish: 0.025,
            entropy_anneal_cycles: 12,
            ppo_num_epochs: 4,
            clip_epsilon: 0.2,
            gae_lambda: 0.95,
            value_coefficient: 0.5,
            max_grad_norm: 0.5,
            minibatch_size: 256,
            env_batch_size: 38,
            device: "auto".into(),
            local_feature_dim: 256,
            lstm_hidden_size: 128,
            mlp_hidden_dim: 256,
            not_finished_reward: -10.0,
            finished_reward: 100.0,
            turn_reward: 0.0,
            frame_step_reward: -0.01,
            tile_exploration_reward: 0.025,
            jump_reward: -0.15,
            jump_reward_polish: -0.5,
            jump_anneal_cycles: 20,
            wall_hugging_reward: -0.2,
            goal_distance_reward_scale: 0.005,
            actions_per_second: 10,
            collect_seconds_per_env: 5,
            max_seconds_per_episode: 60,
            checkpoint_interval: 0,
            seed: 42,
            no_learning: false,
            max_training_levels: 10,
            goal_rehearsal_lock: true,
            goal_rehearsal_epochs: 8,
            goal_rehearsal_scout_episodes: 4,
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
        // Per-tile explore can pay multiple cells per step (brush ≈ 3×3–4×3).
        // Scale by a conservative max footprint so explore does not dominate normalization.
        const MAX_EXPLORE_TILES_PER_STEP: f32 = 12.0;
        [
            self.not_finished_reward,
            self.finished_reward,
            self.turn_reward,
            self.frame_step_reward,
            self.tile_exploration_reward * MAX_EXPLORE_TILES_PER_STEP,
            self.jump_reward,
            self.jump_reward_polish,
            self.wall_hugging_reward,
            self.goal_distance_reward_scale,
        ]
        .into_iter()
        .map(f32::abs)
        .fold(0.0, f32::max)
        .max(1.0)
    }

    /// Effective jump cost for a level given cycles since its first clear (`None` = uncleared).
    pub fn annealed_jump_reward(&self, cycles_since_clear: Option<usize>) -> f32 {
        let Some(elapsed) = cycles_since_clear else {
            return self.jump_reward;
        };
        let span = self.jump_anneal_cycles.max(1) as f32;
        let t = (elapsed as f32 / span).clamp(0.0, 1.0);
        self.jump_reward + t * (self.jump_reward_polish - self.jump_reward)
    }

    /// Effective entropy for the session given cycles since clear (`None` = still discovering).
    pub fn annealed_entropy(&self, cycles_since_clear: Option<usize>) -> f64 {
        let Some(elapsed) = cycles_since_clear else {
            return self.entropy_regularization;
        };
        let span = self.entropy_anneal_cycles.max(1) as f64;
        let t = (elapsed as f64 / span).clamp(0.0, 1.0);
        self.entropy_regularization
            + t * (self.entropy_regularization_polish - self.entropy_regularization)
    }

    /// Clone with an overridden jump reward (used for per-level post-clear anneal).
    pub fn with_jump_reward(&self, jump_reward: f32) -> Self {
        let mut clone = self.clone();
        clone.jump_reward = jump_reward;
        clone
    }

    /// How many collect-window training slots equal one full-length run.
    ///
    /// A run lasts up to `max_seconds_per_episode`; each training collect window
    /// lasts `collect_seconds_per_env` (see trainer loop).
    pub fn episodes_per_run(&self) -> usize {
        (self.max_seconds_per_episode / self.collect_seconds_per_env.max(1)).max(1)
    }

    /// Converts a user-facing run budget into the trainer's episode-slot budget.
    pub fn runs_to_episodes(&self, runs: usize) -> usize {
        runs.saturating_mul(self.episodes_per_run())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn annealed_jump_stays_discovery_until_clear() {
        let mut config = Config::default();
        config.jump_reward = -2.0;
        config.jump_reward_polish = -3.5;
        config.jump_anneal_cycles = 20;
        assert!((config.annealed_jump_reward(None) - (-2.0)).abs() < 1e-6);
        assert!((config.annealed_jump_reward(Some(0)) - (-2.0)).abs() < 1e-6);
    }

    #[test]
    fn annealed_jump_interpolates_then_caps() {
        let mut config = Config::default();
        config.jump_reward = -2.0;
        config.jump_reward_polish = -3.5;
        config.jump_anneal_cycles = 20;
        let mid = config.annealed_jump_reward(Some(10));
        assert!((mid - (-2.75)).abs() < 1e-5);
        assert!((config.annealed_jump_reward(Some(20)) - (-3.5)).abs() < 1e-6);
        assert!((config.annealed_jump_reward(Some(100)) - (-3.5)).abs() < 1e-6);
    }

    #[test]
    fn annealed_entropy_stays_discovery_until_clear() {
        let mut config = Config::default();
        config.entropy_regularization = 0.06;
        config.entropy_regularization_polish = 0.025;
        config.entropy_anneal_cycles = 12;
        assert!((config.annealed_entropy(None) - 0.06).abs() < 1e-9);
        assert!((config.annealed_entropy(Some(0)) - 0.06).abs() < 1e-9);
    }

    #[test]
    fn annealed_entropy_interpolates_then_caps() {
        let mut config = Config::default();
        config.entropy_regularization = 0.06;
        config.entropy_regularization_polish = 0.025;
        config.entropy_anneal_cycles = 12;
        let mid = config.annealed_entropy(Some(6));
        assert!((mid - 0.0425).abs() < 1e-9);
        assert!((config.annealed_entropy(Some(12)) - 0.025).abs() < 1e-9);
        assert!((config.annealed_entropy(Some(100)) - 0.025).abs() < 1e-9);
    }
}
