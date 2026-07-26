# Roadmap & Future Plans

Open / near-term engineering plans. Completed behaviors (weight transfer, CLI `train` overrides, Optuna sequential-mastery `tune`, 25×25 local view, architecture knobs, 3-tile vertical exploration brush, distance guidance reward scale, eval-pack protocols) are documented under [CLI](../cli/index.md), [Engineering](index.md), and [Agentic Fine-Tuning](../agentic_fine_tuning/index.md) — not repeated here.

**Landed recently (engine fine-tune protocol):** Optuna maximizes mean of the lowest `tail_k` per-level play WRs after sequential curriculum + play eval (`eval_runs` default 15); promotion still requires `min ≥ 0.8`; trials use blank agents; `--tune-architecture` is a second pass; `local_view` radius is **12** (625 cells). Stage B neatness is lock + post-clear jump anneal ([How the Intelligence Learns](../intelligence/index.md)). Optional later experiment: 2D conv local encoder. See [Engine Protocol](../agentic_fine_tuning/engine_protocol.md).

---

## 1. Automatic Successful Run Enforcement (Trajectory Solidification)

When a Delver discovers a trajectory that reaches the goal on a new or complex level, early policy weights can still fluctuate before the trajectory is sufficiently solidified into memory.

**Landed (Goal Rehearsal Lock + jump anneal):** when `goal_rehearsal_lock` is true, greedy + stochastic scouts lock the fewest-takeoff victory per level and behavioral-clone it into PPO each cycle (`goal_rehearsal_epochs`, `goal_rehearsal_scout_episodes`). After first clear, per-level `jump_reward` anneals toward `jump_reward_polish` (`jump_anneal_cycles`); `turn_reward` is not annealed. See [Stage B](jump_polish_stage_b.md) and [Run Types](run_types.md) §4.

**Still open:**
- **Automatic Multi-Run Solidification**: optionally force $N$ additional successful rollout cycles once an optimal trajectory is achieved before transitioning.
- Confidence-gated curriculum advance (hold until showcase `policy_confidence` stays above a threshold).

---

## 2. GUI Knobs for Training Parameters

CLI overrides for `intelligence/config.toml` already exist (`train` / `tune`). Next: expose the same knobs in the GUI for players/coaches without raw flags.

Authoritative parameter list: [Commands Reference — train](../cli/commands.md#train). Engine promotion ritual: [Engine Protocol](../agentic_fine_tuning/engine_protocol.md).

---

## 3. Agent Checkpoint Versioning & Milestone Snapshots

Cycle / pre-level checkpoints store **weights + curriculum** bundles (`model_weights.ot` + `curriculum.json`) so restores keep review state aligned. Near-term enhancements:

* **Tagged snapshots** at custom milestones (e.g. `snapshots/after_platform_pack.ot`).
* **Side-by-side compare** of victory rates / curves across tagged snapshots for engine Pass B baselines and player rollbacks.
* **GUI surfacing** of focus-episode progress toward the next automatic review pass.

---

## 4. Parameter Protection & Elastic Weight Consolidation (EWC)

Automatic reviews rehearse prior levels in the PPO mix ([Automatic Reviews](../player/automatic_reviews.md)). A longer-term option is **parameter protection** (e.g. Elastic Weight Consolidation / Synaptic Intelligence): after consolidating a skill, penalize moving important weights so new coaching overwrites them less — without putting every old map back in the mix.

Requires trainer/checkpoint support (importance estimates, consolidation points, $\lambda$ tuning). Often used **alongside** a small amount of replay.

