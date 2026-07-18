mod agent;
mod api;
mod cli;
mod config;
mod cuda_preload;
mod device;
mod environments;
mod level_hash;
mod trainer;

use agent::ppo::Ppo;
use ai_delver_level::Level;
use anyhow::{bail, Context, Result};
use clap::Parser;
use cli::{Cli, Command, TrainArgs, TrainingMode};
use config::Config;
use device::{device_label, resolve_device};
use serde_json::json;
use std::{
    path::PathBuf,
    sync::{atomic::AtomicBool, Arc},
};

fn main() {
    if let Err(error) = run() {
        cli::emit("error", json!({"message": format!("{error:#}")}));
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    cuda_preload::ensure_torch_cuda_loaded();
    let args = Cli::parse();
    match args.command {
        Command::Serve(serve) => {
            let intelligence_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
            let runtime = tokio::runtime::Builder::new_multi_thread()
                .enable_all()
                .build()
                .context("failed to start tokio runtime")?;
            runtime.block_on(api::serve(&serve.host, serve.port, intelligence_root))
        }
        Command::Train(train) => run_train(train),
    }
}

fn run_train(args: TrainArgs) -> Result<()> {
    if matches!(args.mode, TrainingMode::Dynamic) {
        bail!("dynamic curriculum mode is not implemented; use --mode static");
    }
    cli::emit("info", json!({"message": "Starting pure-Rust PPO trainer"}));
    cli::emit(
        "init_started",
        json!({"message": "Loading configuration and levels"}),
    );
    let intelligence_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let repo_root = intelligence_root
        .parent()
        .context("intelligence directory must have repository parent")?;
    let mut config = Config::load(&intelligence_root.join("config.toml"))?;
    apply_overrides(&mut config, &args);
    if let Ok(batch) = std::env::var("AI_BATCH_SIZE") {
        if let Ok(value) = batch.parse::<usize>() {
            config.env_batch_size = value;
        }
    }
    if config.env_batch_size == 0 {
        bail!("environment batch size must be positive");
    }
    let episodes_per_cycle = match args.runs_per_cycle {
        Some(runs) if runs > 0 => config.runs_to_episodes(runs),
        _ => args.episodes_per_cycle,
    };
    if episodes_per_cycle == 0 {
        bail!("run/episode counts must be positive");
    }
    if let Some(runs) = args.runs_per_cycle.filter(|&runs| runs > 0) {
        cli::emit(
            "info",
            json!({
                "message": format!(
                    "Converted {runs} run(s) to {episodes_per_cycle} episode slot(s) per cycle ({} slots/run)",
                    config.episodes_per_run()
                ),
                "runs_per_cycle": runs,
                "episodes_per_cycle": episodes_per_cycle,
                "episodes_per_run": config.episodes_per_run(),
            }),
        );
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
    let on_event = Box::new(|event: &str, value: serde_json::Value| {
        // Redact bulky trajectory blobs; keep one-line NDJSON for scripting.
        cli::emit(event, &value);
    });
    // CLI train resolves levels by path/name; hash from empty placeholder — showcase
    // trajectories from CLI mode are for local debugging only (GUI uses the server).
    let level_hashes = levels.iter().map(|_| String::new()).collect::<Vec<_>>();
    trainer::r#loop::train(
        levels,
        &level_hashes,
        config,
        args.cycles,
        episodes_per_cycle,
        &args.agent,
        checkpoint_interval,
        &intelligence_root.join("data"),
        interrupted,
        ppo,
        device,
        on_event,
    )
}

fn apply_overrides(config: &mut Config, args: &TrainArgs) {
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
