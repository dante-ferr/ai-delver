# Roadmap & Future Plans

Open / near-term engineering plans. Completed behaviors (weight transfer, CLI `train` overrides, Optuna `tune`, 3-tile vertical exploration brush, distance guidance reward scale, eval-pack protocols) are documented under [CLI](../cli/index.md), [Engineering](index.md), and [Agentic Fine-Tuning](../agentic_fine_tuning/index.md) — not repeated here.

---

## 1. Automatic Successful Run Enforcement (Trajectory Solidification)

When a Delver discovers a trajectory that reaches the goal on a new or complex level, early policy weights can still fluctuate before the trajectory is sufficiently solidified into memory.

**Future Feature Plan**:
- **Automatic Multi-Run Solidification**: Implement an option in the training loop to automatically force $N$ additional successful rollout cycles once an optimal trajectory is achieved on a level before transitioning or completing.
- **Goal Rehearsal Lock**: Ensures the policy gradient receives a concentrated batch of high-advantage positive updates on the new solution, preventing early unlearning before curriculum reviews trigger.

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

