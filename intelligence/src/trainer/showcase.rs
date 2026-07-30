use crate::{
    agent::ppo::{Ppo, RehearsalTrajectory},
    config::Config,
    environments::{
        level_env::{DelverPose, LevelEnvironment},
        GLOBAL_STATE_SIZE, LOCAL_VIEW_CELLS,
    },
};
use ai_delver_level::Level;
use anyhow::Result;
use serde_json::{json, Value};
use std::sync::Arc;
use tch::{no_grad, Device, Kind, Tensor};

/// How actions are selected during an evaluation / scout episode.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ActionMode {
    /// Deterministic argmax (GUI showcase / play).
    Greedy,
    /// Stochastic multinomial (Goal Rehearsal Lock scouts).
    Stochastic,
}

/// Result of one episode (trajectory JSON + lock metadata).
#[derive(Clone)]
pub struct ShowcaseResult {
    pub trajectory_json: String,
    pub victorious: bool,
    pub jump_takeoffs: usize,
    pub policy_confidence: f32,
    pub transitions: RehearsalTrajectory,
}

/// Runs one greedy episode (GUI showcase / play eval).
pub fn run_showcase(
    level: Arc<Level>,
    level_hash: &str,
    config: &Config,
    ppo: &Ppo,
    device: Device,
) -> Result<ShowcaseResult> {
    run_episode(level, level_hash, config, ppo, device, ActionMode::Greedy)
}

/// Runs one stochastic scout episode for Goal Rehearsal Lock.
pub fn run_scout(
    level: Arc<Level>,
    level_hash: &str,
    config: &Config,
    ppo: &Ppo,
    device: Device,
) -> Result<ShowcaseResult> {
    run_episode(
        level,
        level_hash,
        config,
        ppo,
        device,
        ActionMode::Stochastic,
    )
}

fn run_episode(
    level: Arc<Level>,
    level_hash: &str,
    config: &Config,
    ppo: &Ppo,
    device: Device,
    mode: ActionMode,
) -> Result<ShowcaseResult> {
    let mut env = LevelEnvironment::new(Arc::clone(&level), Arc::new(config.clone()));
    env.set_augmentations_enabled(false);
    let mut observation = env.reset();
    let mut recurrent = ppo.model.initial_state(1);
    let mut episode_start = 1.0_f32;
    let mut actions = Vec::new();
    let mut frame_snapshots = Vec::new();
    let mut victorious = false;
    let mut total_reward = 0.0_f32;
    let mut jump_takeoffs = 0usize;
    let mut local_data = Vec::new();
    let mut global_data = Vec::new();
    let mut starts_data = Vec::new();
    let mut runs_data = Vec::new();
    let mut jumps_data = Vec::new();
    let max_steps = (config.max_seconds_per_episode * config.actions_per_second).max(1);

    let mut prev_on_ground = true;
    let mut previous_on_air_vy = 0.0_f32;
    frame_snapshots.push(frame_snapshot_from_pose(
        env.delver_pose(),
        prev_on_ground,
        &mut previous_on_air_vy,
    ));
    prev_on_ground = env.delver_pose().is_on_ground;

    let mut total_confidence = 0.0_f32;
    let mut step_count = 0_usize;

    for _ in 0..max_steps {
        local_data.extend_from_slice(&observation.local_view);
        global_data.extend_from_slice(&observation.global_state);
        starts_data.push(episode_start);

        let local = Tensor::from_slice(&observation.local_view)
            .view([1, LOCAL_VIEW_CELLS as i64])
            .to_device(device);
        let global = Tensor::from_slice(&observation.global_state)
            .view([1, GLOBAL_STATE_SIZE as i64])
            .to_device(device);
        let starts = Tensor::from_slice(&[episode_start]).to_device(device);
        let (run_idx, jump_idx, conf) = no_grad(|| match mode {
            ActionMode::Greedy => {
                let (run, jump, conf) = ppo.model.greedy_action_with_confidence(
                    &local,
                    &global,
                    &starts,
                    &mut recurrent,
                );
                let run_idx =
                    Vec::<i64>::try_from(&run.to_device(Device::Cpu).to_kind(Kind::Int64))
                        .expect("run action")[0];
                let jump_idx =
                    Vec::<i64>::try_from(&jump.to_device(Device::Cpu).to_kind(Kind::Int64))
                        .expect("jump action")[0];
                (run_idx, jump_idx, conf)
            }
            ActionMode::Stochastic => {
                let (run, jump, _log_prob, _value) =
                    ppo.model
                        .action_and_value(&local, &global, &starts, &mut recurrent);
                let run_idx =
                    Vec::<i64>::try_from(&run.to_device(Device::Cpu).to_kind(Kind::Int64))
                        .expect("run action")[0];
                let jump_idx =
                    Vec::<i64>::try_from(&jump.to_device(Device::Cpu).to_kind(Kind::Int64))
                        .expect("jump action")[0];
                // Scouts use greedy confidence only as a weak tie-break signal; sample
                // confidence is not comparable, so leave near zero unless later needed.
                (run_idx, jump_idx, 0.0_f32)
            }
        });
        total_confidence += conf;
        step_count += 1;
        runs_data.push(run_idx);
        jumps_data.push(jump_idx);
        actions.push(json!({
            "run": run_idx - 1,
            "jump": jump_idx != 0,
        }));
        let step = env.step(run_idx, jump_idx);
        if step.jump_takeoff {
            jump_takeoffs += 1;
        }
        total_reward += step.reward;
        let pose = env.delver_pose();
        frame_snapshots.push(frame_snapshot_from_pose(
            pose,
            prev_on_ground,
            &mut previous_on_air_vy,
        ));
        prev_on_ground = pose.is_on_ground;
        observation = step.observation;
        episode_start = 0.0;
        if step.done {
            victorious = step.victory;
            break;
        }
    }

    let avg_confidence = if step_count > 0 {
        total_confidence / step_count as f32
    } else {
        0.0
    };

    let trajectory = json!({
        "actions_per_second": config.actions_per_second,
        "victorious": victorious,
        "level_hash": level_hash,
        "total_reward": total_reward,
        "policy_confidence": avg_confidence,
        "jump_takeoffs": jump_takeoffs,
        "delver_actions": actions,
        "frame_snapshots": frame_snapshots,
    });

    Ok(ShowcaseResult {
        trajectory_json: serde_json::to_string(&trajectory)?,
        victorious,
        jump_takeoffs,
        policy_confidence: avg_confidence,
        transitions: RehearsalTrajectory {
            local: local_data,
            global: global_data,
            episode_starts: starts_data,
            runs: runs_data,
            jumps: jumps_data,
            steps: step_count,
        },
    })
}

fn frame_snapshot_from_pose(
    pose: DelverPose,
    prev_on_ground: bool,
    previous_on_air_vy: &mut f32,
) -> Value {
    let (locomotion_state, move_angle, is_moving_intentionally) =
        locomotion_from_pose(pose, prev_on_ground, previous_on_air_vy);
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

/// Matches `SkeletalEntity.LAND_ANIMATION_REQUIRED_FALLING_SPEED`.
const LAND_ANIMATION_REQUIRED_FALLING_SPEED: f32 = -250.0;

fn locomotion_from_pose(
    pose: DelverPose,
    prev_on_ground: bool,
    previous_on_air_vy: &mut f32,
) -> (&'static str, Option<f64>, bool) {
    // Match Delver / SkeletalEntity: rising → JUMP, falling → FALL, hard contact → LAND.
    if !pose.is_on_ground {
        if pose.vy.abs() > 1.0 {
            *previous_on_air_vy = pose.vy;
        }
        if pose.vy > 0.0 {
            return ("JUMP", None, false);
        }
        return ("FALL", None, false);
    }

    if !prev_on_ground {
        let hard_landing = *previous_on_air_vy <= LAND_ANIMATION_REQUIRED_FALLING_SPEED;
        *previous_on_air_vy = 0.0;
        if hard_landing {
            return ("LAND", None, false);
        }
    }

    if pose.action_jump {
        return ("JUMP", None, false);
    }
    if pose.action_run.abs() > 0.1 {
        let angle = if pose.action_run < 0.0 { 180.0 } else { 0.0 };
        return ("RUN", Some(angle), true);
    }
    ("IDLE", None, false)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pose(
        is_on_ground: bool,
        vy: f32,
        action_run: f32,
        action_jump: bool,
    ) -> DelverPose {
        DelverPose {
            x: 0.0,
            y: 0.0,
            vx: 0.0,
            vy,
            is_on_ground,
            action_run,
            action_jump,
        }
    }

    #[test]
    fn locomotion_rising_is_jump_falling_is_fall() {
        let mut air_vy = 0.0;
        let (rising, _, _) =
            locomotion_from_pose(pose(false, 400.0, 0.0, false), true, &mut air_vy);
        let (falling, _, _) =
            locomotion_from_pose(pose(false, -200.0, 0.0, false), true, &mut air_vy);
        assert_eq!(rising, "JUMP");
        assert_eq!(falling, "FALL");
        assert_eq!(air_vy, -200.0);
    }

    #[test]
    fn locomotion_hard_landing_is_land() {
        let mut air_vy = 0.0;
        locomotion_from_pose(pose(false, -300.0, 0.0, false), true, &mut air_vy);
        let (landed, _, _) =
            locomotion_from_pose(pose(true, 0.0, 0.0, false), false, &mut air_vy);
        assert_eq!(landed, "LAND");
        assert_eq!(air_vy, 0.0);
    }

    #[test]
    fn locomotion_soft_landing_skips_land() {
        let mut air_vy = 0.0;
        locomotion_from_pose(pose(false, -100.0, 0.0, false), true, &mut air_vy);
        let (landed, _, _) =
            locomotion_from_pose(pose(true, 0.0, 1.0, false), false, &mut air_vy);
        assert_eq!(landed, "RUN");
    }

    #[test]
    fn locomotion_grounded_jump_action_is_jump() {
        let mut air_vy = 0.0;
        let (state, _, _) =
            locomotion_from_pose(pose(true, 0.0, 0.0, true), true, &mut air_vy);
        assert_eq!(state, "JUMP");
    }

    #[test]
    fn locomotion_grounded_run_and_idle() {
        let mut air_vy = 0.0;
        let (run, angle, moving) =
            locomotion_from_pose(pose(true, 0.0, 1.0, false), true, &mut air_vy);
        assert_eq!(run, "RUN");
        assert_eq!(angle, Some(0.0));
        assert!(moving);

        let (idle, _, _) =
            locomotion_from_pose(pose(true, 0.0, 0.0, false), true, &mut air_vy);
        assert_eq!(idle, "IDLE");
    }
}
