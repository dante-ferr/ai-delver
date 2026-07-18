use clap::{ArgAction, Parser, Subcommand, ValueEnum};
use serde::Serialize;
use std::path::PathBuf;

#[derive(Clone, Copy, Debug, ValueEnum)]
pub enum TrainingMode {
    Static,
    Dynamic,
}

#[derive(Debug, Parser)]
#[command(about = "Pure-Rust PPO trainer and training server for AI Delver")]
pub struct Cli {
    #[command(subcommand)]
    pub command: Command,
}

#[derive(Debug, Subcommand)]
pub enum Command {
    /// Long-lived HTTP/WebSocket server that accepts client training requests.
    Serve(ServeArgs),
    /// One-shot training run (benchmarks / headless jobs).
    Train(TrainArgs),
}

#[derive(Debug, Parser)]
pub struct ServeArgs {
    #[arg(long, default_value = "0.0.0.0")]
    pub host: String,
    #[arg(long, default_value_t = 8001)]
    pub port: u16,
}

#[derive(Debug, Parser)]
pub struct TrainArgs {
    #[arg(long, value_delimiter = ',', required = true)]
    pub levels: Vec<String>,
    #[arg(long, default_value_t = 1)]
    pub cycles: usize,
    /// Full-length run equivalents per cycle. Converted to episode slots using
    /// max_seconds_per_episode / collect_seconds_per_env.
    #[arg(long)]
    pub runs_per_cycle: Option<usize>,
    /// Legacy collect-window slot budget. Ignored when --runs-per-cycle is set.
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
    if event == "showcase" {
        if let Some(map) = object.as_object_mut() {
            if let Some(trajectory) = map.get("trajectory").cloned() {
                let bytes = match &trajectory {
                    serde_json::Value::String(text) => text.len(),
                    other => other.to_string().len(),
                };
                map.insert(
                    "trajectory".into(),
                    serde_json::json!({ "omitted": true, "bytes": bytes }),
                );
            }
        }
    }
    object
        .as_object_mut()
        .expect("object")
        .insert("event".into(), event.into());
    println!("{}", serde_json::to_string(&object).expect("JSON event"));
}

/// Short human-readable line for Docker / operator logs (no bulky payloads).
pub fn log_human(message: impl AsRef<str>) {
    println!("{}", message.as_ref());
}

/// Format a training-loop event as a compact human line, or `None` to stay silent.
pub fn format_human_event(event: &str, value: &serde_json::Value) -> Option<String> {
    match event {
        "metrics" => Some(format!(
            "[metrics] cycle={} step={} loss={:.4} return={:.5} fps={:.0} collect_fps={:.0} episodes={}",
            value.get("cycle").and_then(|v| v.as_u64()).unwrap_or(0),
            value.get("step").and_then(|v| v.as_u64()).unwrap_or(0),
            value.get("loss").and_then(|v| v.as_f64()).unwrap_or(0.0),
            value
                .get("average_return")
                .or_else(|| value.get("reward_mean"))
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0),
            value.get("fps").and_then(|v| v.as_f64()).unwrap_or(0.0),
            value.get("collect_fps").and_then(|v| v.as_f64()).unwrap_or(0.0),
            value.get("episodes").and_then(|v| v.as_u64()).unwrap_or(0),
        )),
        "progress" => Some(format!(
            "[progress] {}",
            value
                .get("message")
                .and_then(|v| v.as_str())
                .unwrap_or("cycle completed")
        )),
        "showcase" => {
            let trajectory = value.get("trajectory");
            let (bytes, victory, frames) = match trajectory {
                Some(serde_json::Value::String(text)) => {
                    let parsed = serde_json::from_str::<serde_json::Value>(text).ok();
                    let victory = parsed
                        .as_ref()
                        .and_then(|t| t.get("victorious").and_then(|v| v.as_bool()))
                        .unwrap_or(false);
                    let frames = parsed
                        .as_ref()
                        .and_then(|t| t.get("frame_snapshots").and_then(|v| v.as_array()))
                        .map(|a| a.len())
                        .unwrap_or(0);
                    (text.len(), victory, frames)
                }
                Some(obj) => {
                    let victory = obj
                        .get("victorious")
                        .and_then(|v| v.as_bool())
                        .unwrap_or(false);
                    let frames = obj
                        .get("frame_snapshots")
                        .and_then(|v| v.as_array())
                        .map(|a| a.len())
                        .unwrap_or(0);
                    (obj.to_string().len(), victory, frames)
                }
                None => (0, false, 0),
            };
            Some(format!(
                "[showcase] level_episode_count={} victory={} frames={} trajectory_bytes={}",
                value
                    .get("level_episode_count")
                    .and_then(|v| v.as_u64())
                    .unwrap_or(0),
                victory,
                frames,
                bytes
            ))
        }
        "checkpoint" => Some(format!(
            "[checkpoint] cycle={} path={}",
            value.get("cycle").and_then(|v| v.as_u64()).unwrap_or(0),
            value.get("path").and_then(|v| v.as_str()).unwrap_or("-")
        )),
        "completed" => Some(format!(
            "[completed] cycles={} checkpoint={}",
            value.get("cycles").and_then(|v| v.as_u64()).unwrap_or(0),
            value
                .get("checkpoint")
                .and_then(|v| v.as_str())
                .unwrap_or("-")
        )),
        "interrupted" => Some(format!(
            "[interrupted] cycle={} checkpoint={}",
            value.get("cycle").and_then(|v| v.as_u64()).unwrap_or(0),
            value
                .get("checkpoint")
                .and_then(|v| v.as_str())
                .unwrap_or("-")
        )),
        "info" | "error" | "init_started" => Some(format!(
            "[{event}] {}",
            value
                .get("message")
                .and_then(|v| v.as_str())
                .unwrap_or(&value.to_string())
        )),
        _ => None,
    }
}
