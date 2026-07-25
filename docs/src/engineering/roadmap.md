# Roadmap & Future Plans

Open / near-term engineering plans. Completed behaviors (weight transfer, CLI `train` overrides, Optuna `tune`, eval-pack protocols) are documented under [CLI](../cli/index.md) and [Agentic Fine-Tuning](../agentic_fine_tuning/index.md) — not repeated here.

---

## 1. GUI knobs for training parameters

CLI overrides for `intelligence/config.toml` already exist (`train` / `tune`). Next: expose the same knobs in the GUI for players/coaches without raw flags.

Authoritative parameter list: [Commands Reference — train](../cli/commands.md#train). Engine promotion ritual: [Engine Protocol](../agentic_fine_tuning/engine_protocol.md).

---

## 2. Agent checkpoint versioning & snapshotting

Cycle / pre-level checkpoints now store **weights + curriculum** bundles (`model_weights.ot` + `curriculum.json`) so restores keep review state aligned. Still useful to add:

* **Tagged snapshots** at custom milestones (e.g. `snapshots/after_platform_pack.ot`).
* **Side-by-side compare** of victory rates / curves across tagged snapshots for engine Pass B baselines and player rollbacks.
* **GUI surfacing** of focus-episode progress toward the next automatic review pass.

---

## 3. Weight protection as an alternative (or complement) to level rehearsal

Automatic reviews rehearse prior levels in the PPO mix ([Automatic Reviews](../player/automatic_reviews.md)). A longer-term option is **parameter protection** (e.g. Elastic Weight Consolidation / Synaptic Intelligence): after consolidating a skill, penalize moving important weights so new coaching overwrites them less — without putting every old map back in the mix.

Would require trainer/checkpoint support (importance estimates, consolidation points, λ tuning). Often used **alongside** a small amount of replay, not as a pure drop-in replacement. Track as a future engine feature if bounded rehearsal is still not enough at 50+ level careers.
