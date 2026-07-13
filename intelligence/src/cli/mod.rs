use clap::{ArgAction, Parser, ValueEnum};
use serde::Serialize;
use std::path::PathBuf;

#[derive(Clone, Copy, Debug, ValueEnum)]
pub enum TrainingMode {
    Static,
    Dynamic,
}

#[derive(Debug, Parser)]
#[command(about = "Pure-Rust PPO trainer for AI Delver")]
pub struct Cli {
    #[arg(long, value_delimiter = ',', required = true)]
    pub levels: Vec<String>,
    #[arg(long, default_value_t = 1)]
    pub cycles: usize,
    #[arg(long, default_value_t = 38)]
    pub episodes_per_cycle: usize,
    #[arg(long, value_enum, default_value_t = TrainingMode::Static)]
    pub mode: TrainingMode,
    #[arg(long, default_value = "default")]
    pub agent: String,
    #[arg(long)]
    pub checkpoint: Option<PathBuf>,
    #[arg(long)]
    pub checkpoint_interval: Option<usize>,
    #[arg(long)]
    pub learning_rate: Option<f64>,
    #[arg(long)]
    pub gamma: Option<f32>,
    #[arg(long)]
    pub entropy_regularization: Option<f64>,
    #[arg(long)]
    pub finished_reward: Option<f32>,
    #[arg(long)]
    pub not_finished_reward: Option<f32>,
    #[arg(long)]
    pub turn_reward: Option<f32>,
    #[arg(long)]
    pub frame_step_reward: Option<f32>,
    #[arg(long)]
    pub tile_exploration_reward: Option<f32>,
    #[arg(long)]
    pub jump_reward: Option<f32>,
    #[arg(long)]
    pub wall_hugging_reward: Option<f32>,
    #[arg(long)]
    pub goal_distance_reward_scale: Option<f32>,
    #[arg(long)]
    pub env_batch_size: Option<usize>,
    #[arg(long)]
    pub device: Option<String>,
    #[arg(long)]
    pub seed: Option<u64>,
    /// Skip policy inference and PPO updates (random actions) for physics profiling.
    #[arg(long, action = ArgAction::SetTrue)]
    pub no_learning: bool,
}

pub fn emit<T: Serialize>(event: &str, value: T) {
    let mut object = serde_json::to_value(value).unwrap_or_default();
    if !object.is_object() {
        object = serde_json::json!({ "value": object });
    }
    object
        .as_object_mut()
        .expect("object")
        .insert("event".into(), event.into());
    println!("{}", serde_json::to_string(&object).expect("JSON event"));
}
