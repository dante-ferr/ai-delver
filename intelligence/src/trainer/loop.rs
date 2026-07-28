use crate::{
    agent::ppo::{Ppo, RehearsalTrajectory, Rollout, UpdateMetrics},
    config::Config,
    environments::{
        level_env::LevelEnvironment, GLOBAL_STATE_SIZE, LOCAL_VIEW_CELLS,
    },
    trainer::showcase::{self, ShowcaseResult},
};
use ai_delver_level::Level;
use anyhow::{Context, Result};
use rayon::prelude::*;
use serde_json::{json, Value};
use std::{
    collections::HashMap,
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

struct RehearsalLock {
    takeoffs: usize,
    confidence: f32,
    trajectory: RehearsalTrajectory,
}

/// Cycles since first clear for a level (`None` = never cleared this session).
type ClearProgress = HashMap<String, usize>;

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
    early_stop: bool,
) -> Result<()> {
    let base_config = Arc::new(config);
    let mut clear_progress: ClearProgress = HashMap::new();
    let rollout_steps = (base_config.actions_per_second * base_config.collect_seconds_per_env).max(1);
    let rollouts_per_cycle = episodes_per_cycle.div_ceil(base_config.env_batch_size).max(1);
    let checkpoint_dir = data_root.join("agents").join(agent_name);
    fs::create_dir_all(&checkpoint_dir)
        .with_context(|| format!("failed to create {}", checkpoint_dir.display()))?;

    // Per-level cleanest victorious trajectory (fewest takeoffs) for Goal Rehearsal Lock.
    let mut rehearsal_locks: HashMap<String, RehearsalLock> = HashMap::new();
    // Consecutive victorious greedy showcases per level hash (early-stop mastery signal).
    let mut victory_streaks: HashMap<String, usize> = HashMap::new();
    // Consecutive greedy showcase fails while in polish (reset anneal after grace).
    let mut polish_fail_streaks: HashMap<String, usize> = HashMap::new();
    let mut recent_returns: Vec<f32> =
        Vec::with_capacity(base_config.early_stop_plateau_window);
    let mut finished_cycles = cycles;

    for cycle in 1..=cycles {
        if interrupted.load(Ordering::Relaxed) {
            let path = save_checkpoint(&ppo, &checkpoint_dir, cycle, "interrupted")?;
            on_event(
                "interrupted",
                json!({"cycle": cycle, "checkpoint": path}),
            );
            return Ok(());
        }

        // Rebuild envs so each level uses its annealed jump_reward for this cycle.
        let mut envs = build_envs(&levels, level_hashes, &base_config, &clear_progress);
        // Entropy is session-wide: discovery until every coach level has cleared, then polish.
        let entropy = base_config.annealed_entropy(session_cycles_since_clear(
            level_hashes,
            &clear_progress,
        ));
        if !base_config.no_learning {
            ppo.set_entropy_regularization(entropy);
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
            let mut observations: Vec<_> = envs.iter_mut().map(LevelEnvironment::reset).collect();
            let mut starts = vec![1.0_f32; envs.len()];
            let mut recurrent = ppo.model.initial_state(envs.len() as i64);
            let collect_began = Instant::now();
            let mut local_data: Vec<f32> =
                Vec::with_capacity(rollout_steps * envs.len() * LOCAL_VIEW_CELLS);
            let mut global_data: Vec<f32> =
                Vec::with_capacity(rollout_steps * envs.len() * GLOBAL_STATE_SIZE);
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
                    .view([envs.len() as i64, LOCAL_VIEW_CELLS as i64])
                    .to_device(device);
                let global = Tensor::from_slice(&step_global)
                    .view([envs.len() as i64, GLOBAL_STATE_SIZE as i64])
                    .to_device(device);
                let start_tensor = Tensor::from_slice(&starts).to_device(device);
                let (runs, jumps, log_probs, values) = if base_config.no_learning {
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
            let bootstrap_values = if base_config.no_learning {
                Tensor::zeros([envs.len() as i64], (Kind::Float, device))
            } else {
                let (_, _, _, values) = no_grad(|| {
                    ppo.model.action_and_value(
                        &Tensor::from_slice(&local)
                            .view([envs.len() as i64, LOCAL_VIEW_CELLS as i64])
                            .to_device(device),
                        &Tensor::from_slice(&global)
                            .view([envs.len() as i64, GLOBAL_STATE_SIZE as i64])
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
                    .view([shape[0], shape[1], LOCAL_VIEW_CELLS as i64])
                    .to_device(device),
                global: Tensor::from_slice(&global_data)
                    .view([shape[0], shape[1], GLOBAL_STATE_SIZE as i64])
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
            last_metrics = if base_config.no_learning {
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

        for (showcase_level, showcase_hash) in levels.iter().zip(level_hashes.iter()) {
            // Collect victorious greedy+scout candidates; lock updates once after scouts.
            let mut lock_candidates: Vec<(ShowcaseResult, String)> = Vec::new();
            let level_cfg = annealed_config_for_hash(
                &base_config,
                showcase_hash,
                &clear_progress,
            );
            match showcase::run_showcase(
                Arc::clone(showcase_level),
                showcase_hash,
                level_cfg.as_ref(),
                &ppo,
                device,
            ) {
                Ok(result) => {
                    if result.victorious {
                        mark_level_cleared(&mut clear_progress, showcase_hash);
                        polish_fail_streaks.insert(showcase_hash.clone(), 0);
                        let streak = victory_streaks.entry(showcase_hash.clone()).or_insert(0);
                        *streak = streak.saturating_add(1);
                        lock_candidates.push((result.clone(), "greedy".to_string()));
                    } else {
                        victory_streaks.insert(showcase_hash.clone(), 0);
                        // Hold polish through polish_fail_grace consecutive greedy misses
                        // so a brittle hard clear is not immediately reheated into discovery.
                        if clear_progress.contains_key(showcase_hash) {
                            let fails = polish_fail_streaks
                                .entry(showcase_hash.clone())
                                .or_insert(0);
                            *fails = fails.saturating_add(1);
                            let grace = base_config.polish_fail_grace.max(1);
                            if *fails >= grace {
                                clear_progress.remove(showcase_hash);
                                polish_fail_streaks.insert(showcase_hash.clone(), 0);
                                on_event(
                                    "info",
                                    json!({
                                        "message": format!(
                                            "Greedy showcase failed {grace}× for {}; returning to discovery jump/explore/entropy band",
                                            showcase_hash
                                        )
                                    }),
                                );
                            } else {
                                on_event(
                                    "info",
                                    json!({
                                        "message": format!(
                                            "Greedy showcase failed for {} ({fails}/{grace}); holding polish anneal + Goal Rehearsal Lock",
                                            showcase_hash
                                        )
                                    }),
                                );
                            }
                        }
                    }
                    on_event(
                        "showcase",
                        json!({
                            "trajectory": result.trajectory_json,
                            "level_episode_count": completed_episodes,
                            "jump_takeoffs": result.jump_takeoffs,
                            "victorious": result.victorious,
                            "policy_confidence": result.policy_confidence
                        }),
                    );
                }
                Err(error) => {
                    victory_streaks.insert(showcase_hash.clone(), 0);
                    polish_fail_streaks.insert(showcase_hash.clone(), 0);
                    clear_progress.remove(showcase_hash);
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

            if base_config.goal_rehearsal_lock && !base_config.no_learning {
                let cycles_since = clear_progress.get(showcase_hash.as_str()).copied();
                let scout_budget = base_config.scout_episodes_for_level(cycles_since);
                for scout_idx in 0..scout_budget {
                    let scout_cfg = annealed_config_for_hash(
                        &base_config,
                        showcase_hash,
                        &clear_progress,
                    );
                    match showcase::run_scout(
                        Arc::clone(showcase_level),
                        showcase_hash,
                        scout_cfg.as_ref(),
                        &ppo,
                        device,
                    ) {
                        Ok(scout) => {
                            if scout.victorious {
                                mark_level_cleared(&mut clear_progress, showcase_hash);
                                polish_fail_streaks.insert(showcase_hash.clone(), 0);
                                lock_candidates
                                    .push((scout, format!("scout-{scout_idx}")));
                            }
                        }
                        Err(error) => {
                            on_event(
                                "info",
                                json!({
                                    "message": format!(
                                        "Goal Rehearsal scout failed for {}: {error:#}",
                                        showcase_hash
                                    )
                                }),
                            );
                        }
                    }
                }
            }

            // Prefer fewest takeoffs among this cycle's victorious greedy+scouts.
            if let Some((best, source)) = lock_candidates
                .into_iter()
                .min_by(|(a, _), (b, _)| {
                    a.jump_takeoffs
                        .cmp(&b.jump_takeoffs)
                        .then_with(|| {
                            b.policy_confidence
                                .partial_cmp(&a.policy_confidence)
                                .unwrap_or(std::cmp::Ordering::Equal)
                        })
                })
            {
                maybe_update_lock(
                    &mut rehearsal_locks,
                    &mut on_event,
                    base_config.as_ref(),
                    showcase_hash,
                    &best,
                    &source,
                );
            }
        }

        // Advance anneal clocks for levels that have already cleared.
        for elapsed in clear_progress.values_mut() {
            *elapsed = elapsed.saturating_add(1);
        }

        if base_config.goal_rehearsal_lock
            && !base_config.no_learning
            && base_config.goal_rehearsal_epochs > 0
        {
            for (_hash, lock) in rehearsal_locks.iter() {
                ppo.rehearse(&lock.trajectory, base_config.goal_rehearsal_epochs);
                if base_config.goal_rehearsal_mirror_clone {
                    let mirrored = lock.trajectory.horizontally_flipped();
                    ppo.rehearse(&mirrored, base_config.goal_rehearsal_epochs);
                }
            }
        }
        if checkpoint_interval > 0 && cycle % checkpoint_interval == 0 {
            let path = save_checkpoint(&ppo, &checkpoint_dir, cycle, "checkpoint")?;
            on_event("checkpoint", json!({"cycle": cycle, "path": path}));
        }

        if early_stop {
            let streak_need = base_config.early_stop_victory_streak;
            let plateau_window = base_config.early_stop_plateau_window;
            let plateau_eps = base_config.early_stop_plateau_eps;
            recent_returns.push(reward_mean);
            if recent_returns.len() > plateau_window {
                recent_returns.remove(0);
            }

            let mastery = level_hashes.iter().all(|hash| {
                victory_streaks.get(hash).copied().unwrap_or(0) >= streak_need
            });
            let all_cleared = level_hashes
                .iter()
                .all(|hash| clear_progress.contains_key(hash));
            let plateau = cycle >= base_config.early_stop_min_cycles
                && all_cleared
                && returns_have_plateaued(&recent_returns, plateau_window, plateau_eps);

            if mastery || plateau {
                let reason = if mastery {
                    format!(
                        "Early-stop: greedy showcase mastery (≥{streak_need} consecutive clears per level)."
                    )
                } else {
                    format!(
                        "Early-stop: average return plateaued after clears (local/global minima)."
                    )
                };
                on_event(
                    "info",
                    json!({
                        "message": reason,
                        "early_stop": true,
                        "cycle": cycle,
                        "mastery": mastery,
                        "plateau": plateau,
                    }),
                );
                finished_cycles = cycle;
                break;
            }
        }
    }
    let path = save_checkpoint(&ppo, &checkpoint_dir, finished_cycles, "final")?;
    on_event(
        "completed",
        json!({
            "cycles": finished_cycles,
            "early_stopped": early_stop && finished_cycles < cycles,
            "checkpoint": path
        }),
    );
    Ok(())
}

fn returns_have_plateaued(recent_returns: &[f32], window: usize, eps: f32) -> bool {
    if recent_returns.len() < window {
        return false;
    }
    let min = recent_returns
        .iter()
        .copied()
        .fold(f32::INFINITY, f32::min);
    let max = recent_returns
        .iter()
        .copied()
        .fold(f32::NEG_INFINITY, f32::max);
    let mean = recent_returns.iter().sum::<f32>() / recent_returns.len() as f32;
    let range = max - min;
    range <= eps * (1.0 + mean.abs())
}

fn build_envs(
    levels: &[Arc<Level>],
    level_hashes: &[String],
    base_config: &Arc<Config>,
    clear_progress: &ClearProgress,
) -> Vec<LevelEnvironment> {
    (0..base_config.env_batch_size)
        .map(|index| {
            let level_index = index % levels.len();
            let hash = level_hashes
                .get(level_index)
                .map(String::as_str)
                .unwrap_or("");
            let cfg = annealed_config_for_hash(base_config, hash, clear_progress);
            LevelEnvironment::new(Arc::clone(&levels[level_index]), cfg)
        })
        .collect()
}

fn annealed_config_for_hash(
    base_config: &Arc<Config>,
    level_hash: &str,
    clear_progress: &ClearProgress,
) -> Arc<Config> {
    let cycles_since = clear_progress.get(level_hash).copied();
    let jump = base_config.annealed_jump_reward(cycles_since);
    let explore = base_config.annealed_explore_reward(cycles_since);
    let mut cfg = base_config.with_annealed_rewards(jump, explore);
    // Cleared levels: mirror-only polish augs (jitter/dropout off, lock-aligned).
    if cycles_since.is_some() {
        cfg = cfg.with_polish_train_augmentations();
    }
    Arc::new(cfg)
}

/// `None` while any coach level is still uncleared; otherwise min cycles-since-clear.
fn session_cycles_since_clear(
    level_hashes: &[String],
    clear_progress: &ClearProgress,
) -> Option<usize> {
    let mut min_elapsed: Option<usize> = None;
    for hash in level_hashes {
        match clear_progress.get(hash) {
            None => return None,
            Some(&elapsed) => {
                min_elapsed = Some(match min_elapsed {
                    None => elapsed,
                    Some(current) => current.min(elapsed),
                });
            }
        }
    }
    min_elapsed
}

fn mark_level_cleared(clear_progress: &mut ClearProgress, level_hash: &str) {
    clear_progress.entry(level_hash.to_string()).or_insert(0);
}

fn maybe_update_lock(
    locks: &mut HashMap<String, RehearsalLock>,
    on_event: &mut EventSink,
    config: &Config,
    level_hash: &str,
    result: &ShowcaseResult,
    source: &str,
) {
    if !config.goal_rehearsal_lock
        || config.no_learning
        || !result.victorious
        || result.transitions.steps == 0
    {
        return;
    }
    let replace = match locks.get(level_hash) {
        None => true,
        Some(best) => {
            result.jump_takeoffs < best.takeoffs
                || (result.jump_takeoffs == best.takeoffs
                    && result.policy_confidence > best.confidence)
        }
    };
    if !replace {
        return;
    }
    locks.insert(
        level_hash.to_string(),
        RehearsalLock {
            takeoffs: result.jump_takeoffs,
            confidence: result.policy_confidence,
            trajectory: result.transitions.clone(),
        },
    );
    on_event(
        "info",
        json!({
            "message": format!(
                "Goal Rehearsal Lock updated for level hash {} via {}: takeoffs={}, confidence={:.3}",
                level_hash,
                source,
                result.jump_takeoffs,
                result.policy_confidence
            )
        }),
    );
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
