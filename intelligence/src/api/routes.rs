use super::{
    session::{ReplayMessage, TrainingSession},
    AppState,
};
use crate::{
    agent::ppo::Ppo,
    config::Config,
    device::resolve_device,
    level_hash::hash_level_json,
    trainer::r#loop::{self as train_loop, EventSink},
};
use ai_delver_level::Level;
use axum::{
    extract::{
        ws::{Message, WebSocket, WebSocketUpgrade},
        Path, State,
    },
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use base64::{engine::general_purpose::STANDARD as BASE64, Engine};
use futures_util::{SinkExt, StreamExt};
use serde::Deserialize;
use serde_json::{json, Value};
use std::{
    fs,
    path::PathBuf,
    sync::{atomic::Ordering, Arc},
};

#[derive(Debug, Deserialize)]
pub struct TrainRequest {
    pub levels: Vec<Value>,
    pub amount_of_cycles: Option<usize>,
    /// Preferred user-facing budget: full-length run equivalents per cycle.
    /// Intelligence converts these into collect-window episode slots.
    #[serde(default)]
    pub runs_per_cycle: Option<usize>,
    /// Legacy / low-level collect-window slot budget. Used when `runs_per_cycle` is absent.
    #[serde(default)]
    pub episodes_per_cycle: Option<usize>,
    pub level_transitioning_mode: String,
    pub config_overrides: Option<Value>,
    pub model_bytes_b64: Option<String>,
}

pub async fn init(State(state): State<Arc<AppState>>) -> Json<Value> {
    Json(json!({
        "message": "AI Delver Intelligence API is up and running.",
        "env_batch_size": state.base_config.env_batch_size,
        "max_training_levels": state.base_config.max_training_levels,
        "collect_seconds_per_env": state.base_config.collect_seconds_per_env,
        "max_seconds_per_episode": state.base_config.max_seconds_per_episode,
        "episodes_per_run": state.base_config.episodes_per_run(),
    }))
}

pub async fn train(
    State(state): State<Arc<AppState>>,
    Json(request): Json<TrainRequest>,
) -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    if request.level_transitioning_mode != "static" {
        return Err((
            StatusCode::BAD_REQUEST,
            Json(json!({
                "message": "dynamic curriculum mode is not implemented; use static"
            })),
        ));
    }
    let cycles = request.amount_of_cycles.unwrap_or(1);
    let has_runs = request.runs_per_cycle.unwrap_or(0) > 0;
    let has_episodes = request.episodes_per_cycle.unwrap_or(0) > 0;
    if cycles == 0 || request.levels.is_empty() || (!has_runs && !has_episodes) {
        return Err((
            StatusCode::BAD_REQUEST,
            Json(json!({
                "message": "levels, amount_of_cycles, and runs_per_cycle (or episodes_per_cycle) must be positive"
            })),
        ));
    }

    let session = state.sessions.create();
    let state_for_job = Arc::clone(&state);
    let session_for_job = Arc::clone(&session);
    let response_id = session.session_id.clone();

    tokio::task::spawn_blocking(move || {
        let session_id = session_for_job.session_id.clone();
        if let Err(error) =
            run_session_training(Arc::clone(&state_for_job), Arc::clone(&session_for_job), request, cycles)
        {
            let _ = session_for_job.event_tx.send(ReplayMessage::Event(json!({
                "type": "error",
                "error_class": "TrainingError",
                "message": format!("{error:#}"),
            })));
        }
        state_for_job.sessions.remove(&session_id);
    });

    Ok(Json(json!({
        "message": "Training started.",
        "session_id": response_id,
    })))
}

pub async fn interrupt_training(
    State(state): State<Arc<AppState>>,
    Path(session_id): Path<String>,
) -> Json<Value> {
    match state.sessions.get(&session_id) {
        Some(session) => {
            session.interrupted.store(true, Ordering::Relaxed);
            Json(json!({
                "message": "Training interrupted.",
                "success": true,
            }))
        }
        None => Json(json!({
            "message": "Session not found.",
            "success": false,
        })),
    }
}

pub async fn episode_trajectory(
    ws: WebSocketUpgrade,
    State(state): State<Arc<AppState>>,
    Path(session_id): Path<String>,
) -> impl IntoResponse {
    let Some(session) = state.sessions.get(&session_id) else {
        return (StatusCode::NOT_FOUND, "Session not found").into_response();
    };
    let Some(receiver) = session.take_receiver() else {
        return (
            StatusCode::CONFLICT,
            "Trajectory stream already consumed for this session",
        )
            .into_response();
    };
    ws.on_upgrade(move |socket| stream_trajectory(socket, session, receiver))
        .into_response()
}

async fn stream_trajectory(
    socket: WebSocket,
    session: Arc<TrainingSession>,
    mut receiver: tokio::sync::mpsc::UnboundedReceiver<ReplayMessage>,
) {
    let interrupted = Arc::clone(&session.interrupted);
    let (mut sender, mut client_messages) = socket.split();

    // Drain the client half so ping/close frames are handled. When the client
    // disconnects (window close, process kill, network drop), stop training.
    let interrupted_on_close = Arc::clone(&interrupted);
    let client_reader = tokio::spawn(async move {
        while let Some(Ok(message)) = client_messages.next().await {
            if matches!(message, Message::Close(_)) {
                break;
            }
        }
        interrupted_on_close.store(true, Ordering::Relaxed);
    });

    while let Some(message) = receiver.recv().await {
        let payload = match message {
            ReplayMessage::End => json!({"end": true}),
            ReplayMessage::Event(value) => value,
        };
        let text = match serde_json::to_string(&payload) {
            Ok(text) => text,
            Err(_) => break,
        };
        if sender.send(Message::Text(text.into())).await.is_err() {
            interrupted.store(true, Ordering::Relaxed);
            break;
        }
        if payload.get("end").and_then(Value::as_bool) == Some(true) {
            break;
        }
    }
    client_reader.abort();
    let _ = sender.close().await;
}

fn run_session_training(
    state: Arc<AppState>,
    session: Arc<TrainingSession>,
    request: TrainRequest,
    cycles: usize,
) -> anyhow::Result<()> {
    let mut config = state.base_config.clone();
    if let Ok(fresh) = Config::load(&state.config_path) {
        config = fresh;
        if let Ok(batch) = std::env::var("AI_BATCH_SIZE") {
            if let Ok(value) = batch.parse::<usize>() {
                config.env_batch_size = value;
            }
        }
    }
    apply_config_overrides(&mut config, request.config_overrides.as_ref());

    let episodes_per_cycle = resolve_episodes_per_cycle(&request, &config)?;
    let _ = session.event_tx.send(ReplayMessage::Event(json!({
        "type": "info",
        "message": format!(
            "Training budget: {} episode slot(s) per cycle ({} run(s) × {} slots/run, or legacy episodes).",
            episodes_per_cycle,
            request.runs_per_cycle.unwrap_or(0),
            config.episodes_per_run()
        ),
        "runs_per_cycle": request.runs_per_cycle,
        "episodes_per_cycle": episodes_per_cycle,
        "episodes_per_run": config.episodes_per_run(),
    })));

    let mut levels = Vec::with_capacity(request.levels.len());
    let mut level_hashes = Vec::with_capacity(request.levels.len());
    for value in &request.levels {
        level_hashes.push(hash_level_json(value));
        let text = serde_json::to_string(value)?;
        levels.push(Arc::new(Level::from_json(&text)?));
    }

    let device = resolve_device(&config.device)?;
    tch::manual_seed(config.seed as i64);
    let mut ppo = Ppo::new(config.clone(), device)?;

    if let Some(encoded) = &request.model_bytes_b64 {
        match try_load_checkpoint_bytes(&mut ppo, encoded, &state.data_root) {
            Ok(path) => {
                let _ = session.event_tx.send(ReplayMessage::Event(json!({
                    "type": "info",
                    "message": format!("Loaded warm-start checkpoint from request ({})", path.display()),
                })));
            }
            Err(error) => {
                let _ = session.event_tx.send(ReplayMessage::Event(json!({
                    "type": "info",
                    "message": format!(
                        "Ignoring model_bytes_b64 (expected libtorch .ot bytes): {error:#}"
                    ),
                })));
            }
        }
    }

    let event_tx = session.event_tx.clone();
    let on_event: EventSink = Box::new(move |event, mut value| {
        if let Some(line) = crate::cli::format_human_event(event, &value) {
            crate::cli::log_human(line);
        }
        match event {
            "metrics" => {
                let payload = json!({
                    "type": "metrics",
                    "step": value.get("step").cloned().unwrap_or(Value::Null),
                    "loss": value.get("loss").cloned().unwrap_or(Value::Null),
                    "average_return": value
                        .get("average_return")
                        .or_else(|| value.get("reward_mean"))
                        .cloned()
                        .unwrap_or(Value::Null),
                    "episodes": value.get("episodes").cloned().unwrap_or(Value::Null),
                });
                let _ = event_tx.send(ReplayMessage::Event(payload));
            }
            "showcase" => {
                // Expand trajectory JSON string to an object for smaller WS framing
                // and simpler client parsing (still accepts string for compatibility).
                if let Some(object) = value.as_object_mut() {
                    object.insert("type".into(), json!("showcase"));
                    if let Some(Value::String(raw)) = object.get("trajectory").cloned() {
                        if let Ok(parsed) = serde_json::from_str::<Value>(&raw) {
                            object.insert("trajectory".into(), parsed);
                        }
                    }
                }
                let _ = event_tx.send(ReplayMessage::Event(value));
            }
            "checkpoint" => {
                let payload = json!({
                    "type": "checkpoint",
                    "cycle": value.get("cycle").cloned().unwrap_or(Value::Null),
                    "model_bytes_b64": checkpoint_to_b64(value.get("path")),
                });
                let _ = event_tx.send(ReplayMessage::Event(payload));
            }
            "completed" | "interrupted" => {
                if let Some(path) = value.get("checkpoint").and_then(Value::as_str) {
                    if let Ok(bytes) = fs::read(path) {
                        let _ = event_tx.send(ReplayMessage::Event(json!({
                            "type": "model_weights",
                            "model_bytes_b64": BASE64.encode(bytes),
                        })));
                    }
                }
            }
            _ => {}
        }
    });

    let checkpoint_interval = config.checkpoint_interval;
    train_loop::train(
        levels,
        &level_hashes,
        config,
        cycles,
        episodes_per_cycle,
        "server",
        checkpoint_interval,
        &state.data_root,
        Arc::clone(&session.interrupted),
        ppo,
        device,
        on_event,
    )?;
    Ok(())
}

/// Prefer `runs_per_cycle` (converted via config timing) over legacy `episodes_per_cycle`.
fn resolve_episodes_per_cycle(request: &TrainRequest, config: &Config) -> anyhow::Result<usize> {
    if let Some(runs) = request.runs_per_cycle.filter(|&runs| runs > 0) {
        return Ok(config.runs_to_episodes(runs).max(1));
    }
    if let Some(episodes) = request.episodes_per_cycle.filter(|&episodes| episodes > 0) {
        return Ok(episodes);
    }
    anyhow::bail!("runs_per_cycle or episodes_per_cycle must be positive")
}

fn checkpoint_to_b64(path: Option<&Value>) -> Value {
    path.and_then(Value::as_str)
        .and_then(|path| fs::read(path).ok())
        .map(|bytes| Value::String(BASE64.encode(bytes)))
        .unwrap_or(Value::Null)
}

fn try_load_checkpoint_bytes(
    ppo: &mut Ppo,
    encoded: &str,
    data_root: &std::path::Path,
) -> anyhow::Result<PathBuf> {
    let bytes = BASE64.decode(encoded.trim())?;
    let dir = data_root.join("agents").join("server").join("uploads");
    fs::create_dir_all(&dir)?;
    let path = dir.join(format!("warm-start-{}.ot", uuid::Uuid::new_v4()));
    fs::write(&path, bytes)?;
    ppo.vs.load(&path)?;
    Ok(path)
}

fn apply_config_overrides(config: &mut Config, overrides: Option<&Value>) {
    let Some(Value::Object(map)) = overrides else {
        return;
    };
    for (key, value) in map {
        match key.as_str() {
            "learning_rate" => {
                if let Some(v) = value.as_f64() {
                    config.learning_rate = v;
                }
            }
            "gamma" => {
                if let Some(v) = value.as_f64() {
                    config.gamma = v as f32;
                }
            }
            "entropy_regularization" => {
                if let Some(v) = value.as_f64() {
                    config.entropy_regularization = v;
                }
            }
            "finished_reward" => {
                if let Some(v) = value.as_f64() {
                    config.finished_reward = v as f32;
                }
            }
            "not_finished_reward" => {
                if let Some(v) = value.as_f64() {
                    config.not_finished_reward = v as f32;
                }
            }
            "turn_reward" => {
                if let Some(v) = value.as_f64() {
                    config.turn_reward = v as f32;
                }
            }
            "frame_step_reward" => {
                if let Some(v) = value.as_f64() {
                    config.frame_step_reward = v as f32;
                }
            }
            "tile_exploration_reward" => {
                if let Some(v) = value.as_f64() {
                    config.tile_exploration_reward = v as f32;
                }
            }
            "jump_reward" => {
                if let Some(v) = value.as_f64() {
                    config.jump_reward = v as f32;
                }
            }
            "wall_hugging_reward" => {
                if let Some(v) = value.as_f64() {
                    config.wall_hugging_reward = v as f32;
                }
            }
            "goal_distance_reward_scale" => {
                if let Some(v) = value.as_f64() {
                    config.goal_distance_reward_scale = v as f32;
                }
            }
            "env_batch_size" => {
                if let Some(v) = value.as_u64() {
                    config.env_batch_size = v as usize;
                }
            }
            "seed" => {
                if let Some(v) = value.as_u64() {
                    config.seed = v;
                }
            }
            "device" => {
                if let Some(v) = value.as_str() {
                    config.device = v.to_string();
                }
            }
            "checkpoint_interval" => {
                if let Some(v) = value.as_u64() {
                    config.checkpoint_interval = v as usize;
                }
            }
            "no_learning" => {
                if let Some(v) = value.as_bool() {
                    config.no_learning = v;
                }
            }
            _ => {}
        }
    }
}
