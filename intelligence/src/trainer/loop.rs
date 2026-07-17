use crate::{
    agent::ppo::{Ppo, Rollout, UpdateMetrics},
    config::Config,
    environments::level_env::LevelEnvironment,
    trainer::showcase,
};
use ai_delver_level::Level;
use anyhow::{Context, Result};
use rayon::prelude::*;
use serde_json::{json, Value};
use std::{
    fs,
    path::Path,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
    time::Instant,
};
use tch::{no_grad, Device, Kind, Tensor};

/// Callback for training lifecycle events (`metrics`, `progress`, `checkpoint`, …).
pub type EventSink = Box<dyn FnMut(&str, Value) + Send>;

pub fn train(
    levels: Vec<Arc<Level>>,
    level_hashes: &[String],
    config: Config,
    cycles: usize,
    episodes_per_cycle: usize,
    agent_name: &str,
    checkpoint_interval: usize,
    data_root: &Path,
    interrupted: Arc<AtomicBool>,
    mut ppo: Ppo,
    device: Device,
    mut on_event: EventSink,
) -> Result<()> {
    let config = Arc::new(config);
    let mut envs: Vec<_> = (0..config.env_batch_size)
        .map(|index| {
            LevelEnvironment::new(
                Arc::clone(&levels[index % levels.len()]),
                Arc::clone(&config),
            )
        })
        .collect();
    let rollout_steps = (config.actions_per_second * config.collect_seconds_per_env).max(1);
    let rollouts_per_cycle = episodes_per_cycle.div_ceil(config.env_batch_size).max(1);
    let checkpoint_dir = data_root.join("agents").join(agent_name);
    fs::create_dir_all(&checkpoint_dir)
        .with_context(|| format!("failed to create {}", checkpoint_dir.display()))?;

    for cycle in 1..=cycles {
        if interrupted.load(Ordering::Relaxed) {
            let path = save_checkpoint(&ppo, &checkpoint_dir, cycle, "interrupted")?;
            on_event(
                "interrupted",
                json!({"cycle": cycle, "checkpoint": path}),
            );
            return Ok(());
        }
        let mut completed_episodes = 0usize;
        let mut victories = 0usize;
        let mut reward_sum = 0.0_f32;
        let mut total_env_steps = 0usize;
        let mut collect_secs = 0.0_f64;
        let mut update_secs = 0.0_f64;
        let mut last_metrics = UpdateMetrics::default();
        let cycle_began = Instant::now();

        for _ in 0..rollouts_per_cycle {
            // Every rollout is a complete recurrent sequence starting from zero state.
            // Resetting here keeps collection and PPO sequence recomputation identical.
            let mut observations: Vec<_> = envs.iter_mut().map(LevelEnvironment::reset).collect();
            let mut starts = vec![1.0_f32; envs.len()];
            let mut recurrent = ppo.model.initial_state(envs.len() as i64);
            let collect_began = Instant::now();
            let mut local_data: Vec<f32> = Vec::with_capacity(rollout_steps * envs.len() * 225);
            let mut global_data: Vec<f32> = Vec::with_capacity(rollout_steps * envs.len() * 7);
            let mut start_data: Vec<f32> = Vec::with_capacity(rollout_steps * envs.len());
            let mut runs_data: Vec<i64> = Vec::with_capacity(rollout_steps * envs.len());
            let mut jumps_data: Vec<i64> = Vec::with_capacity(rollout_steps * envs.len());
            let mut log_probs_data: Vec<f32> = Vec::with_capacity(rollout_steps * envs.len());
            let mut values_data: Vec<f32> = Vec::with_capacity(rollout_steps * envs.len());
            let mut rewards_data: Vec<f32> = Vec::with_capacity(rollout_steps * envs.len());
            let mut dones_data: Vec<f32> = Vec::with_capacity(rollout_steps * envs.len());

            for _ in 0..rollout_steps {
                let step_local: Vec<f32> = observations
                    .iter()
                    .flat_map(|observation| observation.local_view)
                    .collect();
                let step_global: Vec<f32> = observations
                    .iter()
                    .flat_map(|observation| observation.global_state)
                    .collect();
                local_data.extend_from_slice(&step_local);
                global_data.extend_from_slice(&step_global);
                start_data.extend_from_slice(&starts);
                let local = Tensor::from_slice(&step_local)
                    .view([envs.len() as i64, 225])
                    .to_device(device);
                let global = Tensor::from_slice(&step_global)
                    .view([envs.len() as i64, 7])
                    .to_device(device);
                let start_tensor = Tensor::from_slice(&starts).to_device(device);
                let (runs, jumps, log_probs, values) = if config.no_learning {
                    (
                        Tensor::randint(3, [envs.len() as i64], (Kind::Int64, device)),
                        Tensor::randint(2, [envs.len() as i64], (Kind::Int64, device)),
                        Tensor::zeros([envs.len() as i64], (Kind::Float, device)),
                        Tensor::zeros([envs.len() as i64], (Kind::Float, device)),
                    )
                } else {
                    no_grad(|| {
                        ppo.model
                            .action_and_value(&local, &global, &start_tensor, &mut recurrent)
                    })
                };
                let runs_vec = tensor_i64(&runs);
                let jumps_vec = tensor_i64(&jumps);
                let steps: Vec<_> = envs
                    .par_iter_mut()
                    .zip(runs_vec.par_iter().zip(jumps_vec.par_iter()))
                    .map(|(environment, (&run, &jump))| environment.step(run, jump))
                    .collect();
                runs_data.extend(runs_vec);
                jumps_data.extend(jumps_vec);
                log_probs_data.extend(tensor_f32(&log_probs));
                values_data.extend(tensor_f32(&values));
                starts.clear();
                observations.clear();
                for (environment, step) in envs.iter_mut().zip(steps) {
                    reward_sum += step.reward;
                    rewards_data.push(step.reward);
                    dones_data.push(step.done as u8 as f32);
                    if step.done {
                        completed_episodes += 1;
                        victories += step.victory as usize;
                        observations.push(environment.reset());
                        starts.push(1.0);
                    } else {
                        observations.push(step.observation);
                        starts.push(0.0);
                    }
                }
            }

            let local = observations
                .iter()
                .flat_map(|observation| observation.local_view)
                .collect::<Vec<_>>();
            let global = observations
                .iter()
                .flat_map(|observation| observation.global_state)
                .collect::<Vec<_>>();
            let bootstrap_values = if config.no_learning {
                Tensor::zeros([envs.len() as i64], (Kind::Float, device))
            } else {
                let (_, _, _, values) = no_grad(|| {
                    ppo.model.action_and_value(
                        &Tensor::from_slice(&local)
                            .view([envs.len() as i64, 225])
                            .to_device(device),
                        &Tensor::from_slice(&global)
                            .view([envs.len() as i64, 7])
                            .to_device(device),
                        &Tensor::from_slice(&starts).to_device(device),
                        &mut recurrent,
                    )
                });
                values
            };
            collect_secs += collect_began.elapsed().as_secs_f64();
            total_env_steps += rollout_steps * envs.len();
            let shape = [rollout_steps as i64, envs.len() as i64];
            let rollout = Rollout {
                local: Tensor::from_slice(&local_data)
                    .view([shape[0], shape[1], 225])
                    .to_device(device),
                global: Tensor::from_slice(&global_data)
                    .view([shape[0], shape[1], 7])
                    .to_device(device),
                episode_starts: Tensor::from_slice(&start_data)
                    .view(shape)
                    .to_device(device),
                runs: Tensor::from_slice(&runs_data).view(shape).to_device(device),
                jumps: Tensor::from_slice(&jumps_data)
                    .view(shape)
                    .to_device(device),
                old_log_probs: Tensor::from_slice(&log_probs_data)
                    .view(shape)
                    .to_device(device),
                old_values: Tensor::from_slice(&values_data)
                    .view(shape)
                    .to_device(device),
                rewards: Tensor::from_slice(&rewards_data)
                    .view(shape)
                    .to_device(device),
                dones: Tensor::from_slice(&dones_data)
                    .view(shape)
                    .to_device(device),
                bootstrap_values,
            };
            let update_began = Instant::now();
            last_metrics = if config.no_learning {
                UpdateMetrics::default()
            } else {
                ppo.update(rollout)
            };
            update_secs += update_began.elapsed().as_secs_f64();
        }

        let active_secs = cycle_began.elapsed().as_secs_f64();
        let collect_fps = if collect_secs > 0.0 {
            total_env_steps as f64 / collect_secs
        } else {
            0.0
        };
        let overall_fps = if active_secs > 0.0 {
            total_env_steps as f64 / active_secs
        } else {
            0.0
        };
        let reward_mean = reward_sum / total_env_steps.max(1) as f32;
        on_event(
            "metrics",
            json!({
                "cycle": cycle,
                "step": cycle * total_env_steps,
                "loss": last_metrics.loss,
                "policy_loss": last_metrics.policy_loss,
                "value_loss": last_metrics.value_loss,
                "entropy": last_metrics.entropy,
                "reward_mean": reward_mean,
                "average_return": reward_mean,
                "episodes": completed_episodes,
                "victories": victories,
                "fps": overall_fps,
                "collect_fps": collect_fps,
                "collect_s": collect_secs,
                "update_s": update_secs
            }),
        );
        on_event(
            "progress",
            json!({
                "cycle": cycle,
                "level_episode_count": completed_episodes,
                "message": format!("Completed cycle {cycle}")
            }),
        );
        let showcase_level = Arc::clone(&levels[0]);
        let showcase_hash = level_hashes
            .first()
            .map(String::as_str)
            .unwrap_or("");
        match showcase::run_showcase(
            showcase_level,
            showcase_hash,
            config.as_ref(),
            &ppo,
            device,
        ) {
            Ok(trajectory_json) => {
                on_event(
                    "showcase",
                    json!({
                        "trajectory": trajectory_json,
                        "level_episode_count": completed_episodes
                    }),
                );
            }
            Err(error) => {
                on_event(
                    "showcase",
                    json!({
                        "trajectory": Value::Null,
                        "level_episode_count": completed_episodes,
                        "error": format!("{error:#}")
                    }),
                );
            }
        }
        if checkpoint_interval > 0 && cycle % checkpoint_interval == 0 {
            let path = save_checkpoint(&ppo, &checkpoint_dir, cycle, "checkpoint")?;
            on_event("checkpoint", json!({"cycle": cycle, "path": path}));
        }
    }
    let path = save_checkpoint(&ppo, &checkpoint_dir, cycles, "final")?;
    on_event("completed", json!({"cycles": cycles, "checkpoint": path}));
    Ok(())
}

fn save_checkpoint(ppo: &Ppo, directory: &Path, cycle: usize, label: &str) -> Result<String> {
    let path = directory.join(format!("{label}-{cycle}.ot"));
    ppo.vs.save(&path)?;
    Ok(path.display().to_string())
}

fn tensor_f32(tensor: &Tensor) -> Vec<f32> {
    Vec::<f32>::try_from(&tensor.to_device(Device::Cpu).to_kind(Kind::Float)).expect("float tensor")
}

fn tensor_i64(tensor: &Tensor) -> Vec<i64> {
    Vec::<i64>::try_from(&tensor.to_device(Device::Cpu).to_kind(Kind::Int64))
        .expect("integer tensor")
}
