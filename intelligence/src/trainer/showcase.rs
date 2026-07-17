use crate::{
    agent::ppo::Ppo,
    config::Config,
    environments::level_env::{DelverPose, LevelEnvironment},
};
use ai_delver_level::Level;
use anyhow::Result;
use serde_json::{json, Value};
use std::sync::Arc;
use tch::{no_grad, Device, Kind, Tensor};

/// Runs one greedy episode and returns an EpisodeTrajectory-compatible JSON **string**
/// (the client calls `json.loads` on the WebSocket `trajectory` field).
pub fn run_showcase(
    level: Arc<Level>,
    level_hash: &str,
    config: &Config,
    ppo: &Ppo,
    device: Device,
) -> Result<String> {
    let mut env = LevelEnvironment::new(Arc::clone(&level), Arc::new(config.clone()));
    let mut observation = env.reset();
    let mut recurrent = ppo.model.initial_state(1);
    let mut episode_start = 1.0_f32;
    let mut actions = Vec::new();
    let mut frame_snapshots = Vec::new();
    let mut victorious = false;
    let max_steps = (config.max_seconds_per_episode * config.actions_per_second).max(1);

    // Initial pose so interpolation has a start frame before the first action.
    frame_snapshots.push(frame_snapshot_from_pose(env.delver_pose()));

    for _ in 0..max_steps {
        let local = Tensor::from_slice(&observation.local_view)
            .view([1, 225])
            .to_device(device);
        let global = Tensor::from_slice(&observation.global_state)
            .view([1, 7])
            .to_device(device);
        let starts = Tensor::from_slice(&[episode_start]).to_device(device);
        let (run, jump) = no_grad(|| {
            ppo.model
                .greedy_action(&local, &global, &starts, &mut recurrent)
        });
        let run_idx = Vec::<i64>::try_from(&run.to_device(Device::Cpu).to_kind(Kind::Int64))
            .expect("run action")[0];
        let jump_idx = Vec::<i64>::try_from(&jump.to_device(Device::Cpu).to_kind(Kind::Int64))
            .expect("jump action")[0];
        // Discrete heads use {0,1,2} for run and {0,1} for jump; trajectory schema uses
        // run ∈ {-1,0,1} and jump as bool (same mapping as LevelEnvironment::step).
        actions.push(json!({
            "run": run_idx - 1,
            "jump": jump_idx != 0,
        }));
        let step = env.step(run_idx, jump_idx);
        frame_snapshots.push(frame_snapshot_from_pose(env.delver_pose()));
        observation = step.observation;
        episode_start = 0.0;
        if step.done {
            victorious = step.victory;
            break;
        }
    }

    let trajectory = json!({
        "actions_per_second": config.actions_per_second,
        "victorious": victorious,
        "level_hash": level_hash,
        "delver_actions": actions,
        "frame_snapshots": frame_snapshots,
    });
    Ok(serde_json::to_string(&trajectory)?)
}

fn frame_snapshot_from_pose(pose: DelverPose) -> Value {
    let (locomotion_state, move_angle, is_moving_intentionally) = locomotion_from_pose(pose);
    json!({
        "entities": [{
            "entity_id": "delver",
            "entity_type": "SkeletalEntity",
            "position": [pose.x, pose.y],
            "velocity": [pose.vx, pose.vy],
            "angle": 0.0,
            "angular_velocity": 0.0,
            "state": "NORMAL",
            "locomotion_state": locomotion_state,
            "move_angle": move_angle,
            "is_moving_intentionally": is_moving_intentionally,
        }]
    })
}

fn locomotion_from_pose(pose: DelverPose) -> (&'static str, Option<f64>, bool) {
    if pose.action_jump || !pose.is_on_ground {
        if pose.is_on_ground || pose.vy <= 0.0 {
            return ("JUMP", None, false);
        }
        return ("FALL", None, false);
    }
    if pose.action_run.abs() > 0.1 {
        let angle = if pose.action_run < 0.0 { 180.0 } else { 0.0 };
        return ("RUN", Some(angle), true);
    }
    ("IDLE", None, false)
}
