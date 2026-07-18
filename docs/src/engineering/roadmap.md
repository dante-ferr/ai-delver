# Roadmap & Future Plans

Open / near-term engineering plans. Completed behaviors (weight transfer, CLI `train` overrides, Optuna `tune`, eval-pack protocols) are documented under [CLI](../cli/index.md) and [Agentic Fine-Tuning](../agentic_fine_tuning/index.md) — not repeated here.

---

## 1. GUI knobs for training parameters

CLI overrides for `intelligence/config.toml` already exist (`train` / `tune`). Next: expose the same knobs in the GUI for players/coaches without raw flags.

Authoritative parameter list: [Commands Reference — train](../cli/commands.md#train). Engine promotion ritual: [Engine Protocol](../agentic_fine_tuning/engine_protocol.md).

---

## 2. Agent checkpoint versioning & snapshotting

Checkpoints at cycle intervals already exist. Still useful to add:

* **Tagged snapshots** at custom milestones (e.g. `snapshots/after_platform_pack.ot`).
* **Side-by-side compare** of victory rates / curves across tagged snapshots for engine Pass B baselines and player rollbacks.
