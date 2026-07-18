# Agentic Fine-Tuning Protocol (Training Engine)

This protocol tells an **orchestrating AI agent** (or a developer following the same ritual) how to improve the **training engine** — hyperparameters, rewards, defaults in `intelligence/config.toml`, and (when needed) intelligence / runtime architecture so the sim teaches what the game contains.

**It is not the player’s coaching loop.** Growing a Delver’s policy weights is the **player’s** job (GUI / CLI `train` as coach). The agent’s deliverable is a better trainer for those players to use — not a finished Delver model.

Prefer the client CLI over ad-hoc HTTP clients — same rule as the [GUI-to-CLI Integration Protocol](gui_cli_protocol.md).

---

## 0. Roles (do not conflate)

| Actor | Owns | Does *not* own |
| :--- | :--- | :--- |
| **Player (coach)** | Training *their* Delver on levels they care about; warm-starts, curriculum order, when to stop | Shipping project-wide HP defaults or sim architecture |
| **Agentic AI / developer** | Tuning the **engine**: HPs, rewards, `config.toml`, Optuna `tune`, sim support for new mechanics, short **evaluation** trains to measure engine quality | Producing the product’s “capable Delver” as the goal of this protocol |

Evaluation `train` runs that the agent starts are **smoke tests / benchmarks of the engine** (does a blank or fixed agent learn the human eval set under these defaults?). They are not a substitute for player coaching, and their checkpoints are not the shipped player experience unless a developer explicitly decides otherwise.

Near-term engine goal: **platforming learnability** — blank agents make steady progress on the human curriculum pack under current defaults. Later: after traps/enemies/puzzles land in the **training sim**, retune rewards/HPs (and extend the sim) so players can coach those skills too.

---

## 1. Hard rules for engine orchestrators

1. **Orchestrate through the client CLI**, not by inventing ad-hoc HTTP clients:
   ```bash
   cd client
   poetry run python src/cli/main.py <command> ...
   ```
2. **Ensure the training server is up** before `train` / `tune` (default `localhost:8001`):
   ```bash
   # from repo root
   make run-ai-dev
   ```
3. **Use `--mode static` only.** Dynamic curriculum still errors on the server.
4. **Parse JSON lines on stdout.** Every lifecycle signal is a single JSON object with an `event` field.
5. **Prefer `--runs-per-cycle`** for human-facing train docs; `tune` may still use `--episodes-per-cycle` (align to `env_batch_size` from `GET /init`).
6. **Do not treat “ship a strong Delver checkpoint” as success** for this protocol. Success is better defaults / a healthier learning curve on the eval set.
7. **Do not invent complex level layouts.** Use human-authored eval / curriculum levels — [Level Authoring Protocol](level_authoring_protocol.md).
8. **Do not call the intelligence API from GUI or one-off scripts** for lifecycle actions—extend the CLI instead.

Command reference: [CLI Commands Reference](cli_commands.md). Player-side curriculum / forgetting: [Curriculum & Forgetting Prevention](curriculum_and_forgetting.md).

---

## 2. What to change (engine surface)

| Lever | Where | When |
| :--- | :--- | :--- |
| Learning rate, entropy, PPO knobs | `intelligence/config.toml` and/or CLI overrides | Instability, no learning, or after `tune` |
| Reward weights | `config.toml` / CLI | Wrong incentives (goal ignored, wall-hugging, etc.) |
| Collect / episode timing | `config.toml` | Eval signal too noisy or too slow |
| Optuna search | CLI `tune` | Systematic HP search after a big change |
| Training sim (platforms/traps/…) | `intelligence` + `runtime` / level load | New mechanic exists in editor but is ignored in rollouts |
| Physics feel (jump, gaps) | `delver.toml` / `world.toml` | Rare; also re-run `platforming-limits` and warn humans to re-check levels |

Document non-obvious default changes with comments in `config.toml` (why this value).

---

## 3. Hyperparameter search (`tune`)

Primary tool for **engine** fine-tuning. Optuna maximizes **win rate** on a short static train per trial.

### Behavior

`tune` (`client/src/cli/commands/tune.py`):

1. Creates an Optuna study that maximizes win rate.
2. Each trial suggests `learning_rate`, `entropy_reg`, `finished_reward` (ranges in `tune.py`).
3. Spawns `train ... --mode static` with those overrides.
4. Prunes a trial early if `metrics` reports `abs(loss) > 20`.
5. Emits `completed` with `best_params` / `best_value`.

### Invocation

```bash
cd client
poetry run python src/cli/main.py tune \
    --levels "Eval Gap A,Eval Rise A" \
    --cycles 5 \
    --episodes-per-cycle 38 \
    --agent engine_eval_agent \
    --trials 10 \
    --server localhost:8001
```

Use a **human-authored representative eval set** (see level authoring pack). Prefer `--episodes-per-cycle` = `env_batch_size` so trials are not silently rounded.

### After `tune`

1. Read `best_params` from the final `completed` event.
2. **Promote into project defaults** when they beat the current baseline on a longer evaluation train (update `intelligence/config.toml` with a short comment).
3. Optionally confirm with one longer smoke `train` under the new defaults (still an engine check, not player coaching).
4. Do **not** treat `tune` as a substitute for sim feature work.

### Caveats

- Search ranges live in `tune.py`. Shipped `entropy_regularization` in `config.toml` may sit outside the Optuna band — sanity-check before promoting.
- Keep eval agents / folders separate from any personal “play” agents if you care about clean bookkeeping.

---

## 4. Evaluation `train` (engine smoke test only)

Short `train` sessions are allowed **to measure whether the engine learns**, not to finish a product Delver.

```bash
cd client
poetry run python src/cli/main.py train \
    --levels "Eval Walk,Eval Gap A,Eval Rise A" \
    --cycles 5 \
    --runs-per-cycle 5 \
    --mode static \
    --agent engine_eval_agent \
    --server localhost:8001
```

### Engine success criteria (platforming)

The **engine** is good enough to hand to players when, under current defaults and the human eval pack:

1. Runs complete without `error`.
2. `stats` / metrics show a clear rise in victories (or return) vs a known-bad baseline or early cycles.
3. Changes promoted to `config.toml` are commented and reproducible.
4. (After a mechanic lands in the sim) blank or warm-start eval agents can make progress on levels that use that mechanic — again as an engine check.

Player success (“my Delver cleared my custom map”) is out of scope here.

### Useful CLI automation (for eval runs)

- Batch-size alignment, level prepare/hash, weight upload, checkpoint download, `stats`
- New-challenge LR scaling when warm-starting onto unseen level names (relevant if an eval agent carries weights between engine experiments)

Events: `session_created`, `progress`, `metrics`, `checkpoint`, `completed` / `interrupted`, `error`, `stats` — same JSON contracts as player `train`.

---

## 5. When new big features are added (engine ritual)

Adding enemies, traps, puzzles, etc. is a **developer / agent engine ritual**. Players will coach Delvers on those features later; first the trainer must simulate them and have sane rewards/HPs.

```text
implement feature in editor + training sim
        → retune engine (rewards / HPs / tune)
        → confirm eval learnability
        → players coach Delvers with the improved engine
```

### Required order

1. **Land the feature in the training environment**  
   Extend level loading and physics/observations so new objects affect rollouts. Today training only keeps platforms, one delver, and one goal; other world-object names are ignored until simulated.

2. **Retune the engine**  
   Adjust rewards / HPs; run `tune` on a small human eval set that exercises the new mechanic (prefer **combo** maps: platforming + new feature — see [Curriculum & Forgetting Prevention](curriculum_and_forgetting.md)).

3. **Confirm engine quality**  
   Short evaluation trains: progress on new-feature levels and no catastrophic collapse on older platforming eval levels.

4. **Optional**  
   Document new defaults; only then invite players to coach with the updated engine.

### What does *not* require this ritual

| Change | Action |
| :--- | :--- |
| New platform **layouts** only | No engine change; players (or eval) just `train` on new names |
| HP / reward tweak only | `tune` and/or short eval `train`; promote defaults if better |
| Mechanic in editor but **not** in training sim | Do not tune yet — extend the sim first |

---

## 6. Levels for engine work

**Humans author levels.** Agents validate spacing (`platforming-limits`), may import sketches, and use them as the **eval / curriculum pack** for `tune` and smoke trains.

Full rules and the recommended **~8–11 level platforming pack**: [Level Authoring Protocol](level_authoring_protocol.md).

Sketch import (when the human used a sketch):

```bash
poetry run python src/cli/main.py import-level-sketch \
    --from "data/level_sketches/Some Eval.json" \
    --name "Some Eval"
```

Schema details: [Level Authoring Protocol](level_authoring_protocol.md) and sketch notes below if you need the grid format.

### Sketch schema (reference)

```json
{
  "name": "Eval Gap A",
  "grid_size": [20, 12],
  "cells": [
    [null, null, "platform"],
    ["delver", null, "goal"]
  ]
}
```

| Rule | Detail |
| :--- | :--- |
| IDs | `platform`, `delver`, `goal` only (MVP) |
| Concurrent layers | No `platform` + `delver`/`goal` in one cell |
| Uniques | Exactly one `delver` and one `goal` **anchor**, both interior |
| Footprints | Anchors are **bottom-left**. Delver is currently **1×3**; Goal is **2×2** (body above/right of the standing cell) |
| Borders | Perimeter sealed with `platform` on import |

---

## 7. Minimal engine-orchestrator checklist

```text
[ ] Human eval / curriculum levels available (do not invent complex layouts)
[ ] platforming-limits if reviewing spacing or after physics TOML changes
[ ] Server up (serve / make run-ai-dev)
[ ] Decide change: config HPs/rewards vs sim architecture vs both
[ ] If new mechanic: sim support first
[ ] tune on representative eval levels (optional but preferred after big changes)
[ ] Promote best_params to config.toml with comments when justified
[ ] Short eval train under new defaults; check stats / metrics (engine quality)
[ ] Do not conflate eval checkpoints with “the” player Delver
```

For subprocess wiring and JSON event patterns shared with the GUI, see [GUI-to-CLI Integration Protocol](gui_cli_protocol.md).
