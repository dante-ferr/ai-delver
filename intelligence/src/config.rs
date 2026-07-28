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
    /// Discovery-band explore pay (before first clear).
    pub tile_exploration_reward: f32,
    /// Post-clear explore target (lower → less hop-into-air farming after invent).
    pub tile_exploration_reward_polish: f32,
    /// Cycles after first clear to reach `tile_exploration_reward_polish`.
    pub explore_anneal_cycles: usize,
    pub jump_reward: f32,
    /// Post-clear jump cost target (typically more negative than `jump_reward`).
    /// After a level's first victory, `jump_reward` anneals toward this over
    /// `jump_anneal_cycles`. Not applied to turn_reward (mazes need cheap turns).
    pub jump_reward_polish: f32,
    /// Cycles after first clear to fully reach `jump_reward_polish`.
    pub jump_anneal_cycles: usize,
    /// Consecutive greedy showcase fails before resetting polish anneal to discovery.
    /// Misses inside the grace keep polish + Goal Rehearsal Lock.
    pub polish_fail_grace: usize,
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
    /// Stochastic scout episodes per level per cycle before first clear.
    pub goal_rehearsal_scout_episodes: usize,
    /// Scout episodes per level per cycle after that level has cleared.
    pub goal_rehearsal_scout_episodes_polish: usize,
    /// When true, each locked traj is also rehearsed as a horizontal mirror clone.
    pub goal_rehearsal_mirror_clone: bool,
    /// Consecutive victorious greedy showcases per level before early-stop mastery.
    pub early_stop_victory_streak: usize,
    /// Minimum cycles before return-plateau early-stop can fire.
    pub early_stop_min_cycles: usize,
    /// Rolling window of `average_return` samples used for plateau detection.
    pub early_stop_plateau_window: usize,
    /// Relative range (`(max-min) / (1+|mean|)`) below which returns count as flat.
    pub early_stop_plateau_eps: f32,
    /// Enable spatial & sensory data augmentations during training.
    pub enable_augmentations: bool,
    /// Probability of horizontally flipping rollouts during discovery training.
    pub mirror_augmentation_prob: f32,
    /// Mirror probability for cleared-level (polish) train collect.
    pub mirror_augmentation_prob_polish: f32,
    /// Spawn position jitter radius in pixels.
    pub spawn_jitter_px: f32,
    /// Goal offset target noise magnitude in normalized units.
    pub goal_jitter_norm: f32,
    /// Probability of masking individual local_view occupancy cells.
    pub local_view_dropout_prob: f32,
}

#[cfg(test)]
impl Default for Config {
    fn default() -> Self {
        Self {
            learning_rate: 3e-4,
            gamma: 0.995,
            entropy_regularization: 0.075,
            entropy_regularization_polish: 0.02,
            entropy_anneal_cycles: 6,
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
            tile_exploration_reward: 0.075,
            tile_exploration_reward_polish: 0.02,
            explore_anneal_cycles: 6,
            jump_reward: -0.15,
            jump_reward_polish: -0.5,
            jump_anneal_cycles: 10,
            polish_fail_grace: 3,
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
            goal_rehearsal_scout_episodes_polish: 10,
            goal_rehearsal_mirror_clone: true,
            early_stop_victory_streak: 5,
            early_stop_min_cycles: 15,
            early_stop_plateau_window: 8,
            early_stop_plateau_eps: 0.01,
            enable_augmentations: true,
            mirror_augmentation_prob: 0.5,
            mirror_augmentation_prob_polish: 0.5,
            spawn_jitter_px: 2.0,
            goal_jitter_norm: 0.02,
            local_view_dropout_prob: 0.01,
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
            self.tile_exploration_reward_polish * MAX_EXPLORE_TILES_PER_STEP,
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
        Self::anneal_f32(
            self.jump_reward,
            self.jump_reward_polish,
            self.jump_anneal_cycles,
            cycles_since_clear,
        )
    }

    /// Effective explore pay for a level given cycles since its first clear.
    pub fn annealed_explore_reward(&self, cycles_since_clear: Option<usize>) -> f32 {
        Self::anneal_f32(
            self.tile_exploration_reward,
            self.tile_exploration_reward_polish,
            self.explore_anneal_cycles,
            cycles_since_clear,
        )
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

    /// Scout budget for a level: polish count after clear, discovery count before.
    pub fn scout_episodes_for_level(&self, cycles_since_clear: Option<usize>) -> usize {
        if cycles_since_clear.is_some() {
            self.goal_rehearsal_scout_episodes_polish
        } else {
            self.goal_rehearsal_scout_episodes
        }
    }

    fn anneal_f32(
        discovery: f32,
        polish: f32,
        cycles: usize,
        cycles_since_clear: Option<usize>,
    ) -> f32 {
        let Some(elapsed) = cycles_since_clear else {
            return discovery;
        };
        let span = cycles.max(1) as f32;
        let t = (elapsed as f32 / span).clamp(0.0, 1.0);
        discovery + t * (polish - discovery)
    }

    /// Clone with per-level annealed jump + explore (post-clear polish).
    pub fn with_annealed_rewards(&self, jump_reward: f32, tile_exploration_reward: f32) -> Self {
        let mut clone = self.clone();
        clone.jump_reward = jump_reward;
        clone.tile_exploration_reward = tile_exploration_reward;
        clone
    }

    /// Post-clear train collect: keep mirror, zero jitter/dropout (lock-aligned).
    pub fn with_polish_train_augmentations(&self) -> Self {
        let mut clone = self.clone();
        clone.enable_augmentations = true;
        clone.mirror_augmentation_prob = self.mirror_augmentation_prob_polish;
        clone.spawn_jitter_px = 0.0;
        clone.goal_jitter_norm = 0.0;
        clone.local_view_dropout_prob = 0.0;
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
        config.entropy_regularization = 0.075;
        config.entropy_regularization_polish = 0.02;
        config.entropy_anneal_cycles = 8;
        assert!((config.annealed_entropy(None) - 0.075).abs() < 1e-9);
        assert!((config.annealed_entropy(Some(0)) - 0.075).abs() < 1e-9);
    }

    #[test]
    fn annealed_entropy_interpolates_then_caps() {
        let mut config = Config::default();
        config.entropy_regularization = 0.075;
        config.entropy_regularization_polish = 0.02;
        config.entropy_anneal_cycles = 8;
        let mid = config.annealed_entropy(Some(4));
        assert!((mid - 0.0475).abs() < 1e-9);
        assert!((config.annealed_entropy(Some(8)) - 0.02).abs() < 1e-9);
        assert!((config.annealed_entropy(Some(100)) - 0.02).abs() < 1e-9);
    }

    #[test]
    fn annealed_explore_interpolates_then_caps() {
        let mut config = Config::default();
        config.tile_exploration_reward = 0.075;
        config.tile_exploration_reward_polish = 0.02;
        config.explore_anneal_cycles = 8;
        assert!((config.annealed_explore_reward(None) - 0.075).abs() < 1e-6);
        let mid = config.annealed_explore_reward(Some(4));
        assert!((mid - 0.0475).abs() < 1e-5);
        assert!((config.annealed_explore_reward(Some(8)) - 0.02).abs() < 1e-6);
    }

    #[test]
    fn scout_budget_switches_after_clear() {
        let mut config = Config::default();
        config.goal_rehearsal_scout_episodes = 4;
        config.goal_rehearsal_scout_episodes_polish = 10;
        assert_eq!(config.scout_episodes_for_level(None), 4);
        assert_eq!(config.scout_episodes_for_level(Some(0)), 10);
        assert_eq!(config.scout_episodes_for_level(Some(3)), 10);
    }

    #[test]
    fn polish_train_augs_keep_mirror_zero_jitter() {
        let mut config = Config::default();
        config.mirror_augmentation_prob = 0.5;
        config.mirror_augmentation_prob_polish = 0.5;
        config.spawn_jitter_px = 2.0;
        config.goal_jitter_norm = 0.02;
        config.local_view_dropout_prob = 0.01;
        let polish = config.with_polish_train_augmentations();
        assert!(polish.enable_augmentations);
        assert!((polish.mirror_augmentation_prob - 0.5).abs() < 1e-6);
        assert_eq!(polish.spawn_jitter_px, 0.0);
        assert_eq!(polish.goal_jitter_norm, 0.0);
        assert_eq!(polish.local_view_dropout_prob, 0.0);
    }
}
