mod agent;
mod cli;
mod config;
mod cuda_preload;
mod environments;
mod trainer;

use agent::ppo::Ppo;
use ai_delver_level::Level;
use anyhow::{bail, Context, Result};
use clap::Parser;
use cli::{Cli, TrainingMode};
use config::Config;
use serde_json::json;
use std::{
    path::PathBuf,
    sync::{atomic::AtomicBool, Arc},
};
use tch::Device;

fn main() {
    if let Err(error) = run() {
        cli::emit("error", json!({"message": format!("{error:#}")}));
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    cuda_preload::ensure_torch_cuda_loaded();
    let args = Cli::parse();
    if matches!(args.mode, TrainingMode::Dynamic) {
        bail!("dynamic curriculum mode is not implemented; use --mode static");
    }
    cli::emit("info", json!({"message": "Starting pure-Rust PPO trainer"}));
    cli::emit(
        "init_started",
        json!({"message": "Loading configuration and levels"}),
    );
    let intelligence_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .context("crate must be inside intelligence/")?
        .to_path_buf();
    let repo_root = intelligence_root
        .parent()
        .context("intelligence directory must have repository parent")?;
    let mut config = Config::load(&intelligence_root.join("src/ai/config.toml"))?;
    apply_overrides(&mut config, &args);
    if config.env_batch_size == 0 || args.episodes_per_cycle == 0 {
        bail!("environment and episode counts must be positive");
    }
    let device = resolve_device(&config.device)?;
    cli::emit(
        "info",
        json!({
            "message": format!("Using device {}", device_label(device)),
            "device": device_label(device),
            "cuda_available": tch::Cuda::is_available(),
        }),
    );
    tch::manual_seed(config.seed as i64);
    let levels = args
        .levels
        .iter()
        .map(|input| {
            let path = Level::resolve(input, repo_root)?;
            Ok(Arc::new(Level::load(&path)?))
        })
        .collect::<Result<Vec<_>>>()?;
    cli::emit(
        "info",
        json!({"message": "Levels loaded", "levels": levels.iter().map(|level| &level.name).collect::<Vec<_>>() }),
    );
    let mut ppo = Ppo::new(config.clone(), device)?;
    if let Some(checkpoint) = &args.checkpoint {
        ppo.vs
            .load(checkpoint)
            .with_context(|| format!("failed to load checkpoint {}", checkpoint.display()))?;
    }
    let interrupted = Arc::new(AtomicBool::new(false));
    let signal = Arc::clone(&interrupted);
    ctrlc::set_handler(move || {
        signal.store(true, std::sync::atomic::Ordering::Relaxed);
    })
    .context("failed to install Ctrl-C handler")?;
    let checkpoint_interval = args
        .checkpoint_interval
        .unwrap_or(config.checkpoint_interval);
    trainer::r#loop::train(
        levels,
        config,
        args.cycles,
        args.episodes_per_cycle,
        &args.agent,
        checkpoint_interval,
        &intelligence_root.join("data"),
        interrupted,
        ppo,
        device,
    )
}

fn apply_overrides(config: &mut Config, args: &Cli) {
    macro_rules! override_value {
        ($field:ident) => {
            if let Some(value) = args.$field {
                config.$field = value;
            }
        };
    }
    override_value!(learning_rate);
    override_value!(gamma);
    override_value!(entropy_regularization);
    override_value!(finished_reward);
    override_value!(not_finished_reward);
    override_value!(turn_reward);
    override_value!(frame_step_reward);
    override_value!(tile_exploration_reward);
    override_value!(jump_reward);
    override_value!(wall_hugging_reward);
    override_value!(goal_distance_reward_scale);
    override_value!(env_batch_size);
    override_value!(seed);
    if let Some(value) = &args.device {
        config.device.clone_from(value);
    }
    if args.no_learning {
        config.no_learning = true;
    }
}

fn resolve_device(value: &str) -> Result<Device> {
    match value.to_ascii_lowercase().as_str() {
        "auto" => {
            let device = Device::cuda_if_available();
            if matches!(device, Device::Cpu) {
                cli::emit(
                    "info",
                    json!({"message": "No CUDA device available; falling back to CPU"}),
                );
            }
            Ok(device)
        }
        "cpu" => Ok(Device::Cpu),
        "cuda" => {
            if !tch::Cuda::is_available() {
                bail!("device cuda requested but CUDA is not available in this libtorch build");
            }
            Ok(Device::Cuda(0))
        }
        "mps" => Ok(Device::Mps),
        value if value.starts_with("cuda:") => {
            if !tch::Cuda::is_available() {
                bail!("device {value} requested but CUDA is not available in this libtorch build");
            }
            Ok(Device::Cuda(
                value[5..]
                    .parse()
                    .context("invalid CUDA device index")?,
            ))
        }
        _ => bail!("device must be auto, cpu, cuda, cuda:N, or mps"),
    }
}

fn device_label(device: Device) -> String {
    match device {
        Device::Cpu => "cpu".into(),
        Device::Cuda(index) => format!("cuda:{index}"),
        Device::Mps => "mps".into(),
        Device::Vulkan => "vulkan".into(),
    }
}
