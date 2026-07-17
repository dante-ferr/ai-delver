mod routes;
mod session;

use crate::config::Config;
use anyhow::{Context, Result};
use axum::{
    extract::DefaultBodyLimit,
    routing::{get, post},
    Router,
};
use session::SessionManager;
use std::{net::SocketAddr, path::PathBuf, sync::Arc};
use tokio::net::TcpListener;
use tower_http::cors::CorsLayer;

/// Train payloads include full level JSON plus optional base64 weights.
/// Axum's default 2 MiB limit is far too small for that.
const MAX_REQUEST_BODY_BYTES: usize = 64 * 1024 * 1024;

#[derive(Clone)]
pub struct AppState {
    pub sessions: SessionManager,
    pub config_path: PathBuf,
    pub data_root: PathBuf,
    pub base_config: Config,
}

pub async fn serve(host: &str, port: u16, intelligence_root: PathBuf) -> Result<()> {
    let config_path = intelligence_root.join("config.toml");
    let mut base_config = Config::load(&config_path)?;
    if let Ok(batch) = std::env::var("AI_BATCH_SIZE") {
        if let Ok(value) = batch.parse::<usize>() {
            base_config.env_batch_size = value;
        }
    }
    let state = Arc::new(AppState {
        sessions: SessionManager::new(),
        config_path,
        data_root: intelligence_root.join("data"),
        base_config,
    });

    let app = Router::new()
        .route("/init", get(routes::init))
        .route("/train", post(routes::train))
        .route(
            "/interrupt-training/{session_id}",
            post(routes::interrupt_training),
        )
        .route(
            "/episode-trajectory/{session_id}",
            get(routes::episode_trajectory),
        )
        .layer(DefaultBodyLimit::max(MAX_REQUEST_BODY_BYTES))
        .layer(CorsLayer::permissive())
        .with_state(state);

    let addr: SocketAddr = format!("{host}:{port}")
        .parse()
        .with_context(|| format!("invalid listen address {host}:{port}"))?;
    let listener = TcpListener::bind(addr)
        .await
        .with_context(|| format!("failed to bind {addr}"))?;
    crate::cli::log_human(format!(
        "[info] Training server listening on http://{addr}"
    ));
    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await
        .context("training server exited with error")?;
    Ok(())
}

async fn shutdown_signal() {
    let _ = tokio::signal::ctrl_c().await;
    crate::cli::log_human("[info] Shutdown signal received; stopping training server");
}
