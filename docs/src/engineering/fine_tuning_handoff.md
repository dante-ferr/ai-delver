# Fine-Tuning Discussion Handoff & Protocol Evolution

This document serves as the **authoritative handoff record** for resuming the AI Delver Intelligence Fine-Tuning discussion in a new conversation context.

---

## 1. Core User Directives & Philosophy

> [!IMPORTANT]
> **1. Enforce Full Level Mastery (100% / >80%+ Clear Rate)**:
> `platforming-1` through `platforming-10` are foundational platforming levels. The fine-tuning protocol must **not** accept a diluted average win rate (e.g. 9%). It must enforce actual sequential mastery across all 10 levels before declaring a hyperparameter set "ideal."

> [!IMPORTANT]
> **2. Full LLM Orchestrator Liberty**:
> Fine-tuning is intended to be executed only **once per skill family**. Long tuning run durations are 100% acceptable. The orchestrating LLM agent should have full liberty to tune Optuna settings, trial budgets, reward spaces, and **Neural Network Architecture** (e.g., LSTM state sizes, feature dimensions, PPO epoch counts, minibatch sizes) — architecture search as a **second pass** after rewards stabilize.

> [!IMPORTANT]
> **3. Pure Vision-Based RL (Zero Artificial Rules/Shortcuts)**:
> The user strictly **rejects** artificial conditional rules or heuristic overrides. The Delver MUST learn to navigate, jump, turn around, and explore **purely through its 25×25 visual window (`local_view`, radius 12 → 625 inputs)** plus `global_state` proprioception / relative goal.

> [!IMPORTANT]
> **4. Preserve Real Game Mechanics**:
> - **Standing Still**: Must remain unpenalized (to preserve future elevator, moving platform, and physics timing mechanics).
> - **Backtracking / Turning Around**: Must remain unpenalized to support maze navigation and multi-room levels.

---

## 2. Current Codebase State & Accomplished Features

### A. Intelligence Engine (Rust)
- **3-Tile Vertical Span Exploration Brush** (`exploration.rs` & `level_env.rs`):
  Sweeps the Delver's 38px (3-tile) physical height footprint (`feet_ty` to `head_ty`). Flat-ground hops yield `newly_explored = false`, mathematically eliminating flat-ground jump exploration farming.
- **Wall Hugging Grace Period** (`reward.rs`):
  10-frame (1.0s) grace period before `wall_hugging_reward` can trigger. Brief wall contact during running, landing, or falling carries $0.0$ penalty.
- **Policy Confidence Metric** (`model.rs` & `showcase.rs`):
  Implemented `greedy_action_with_confidence()` in `model.rs` and attached `"policy_confidence"` to showcase trajectory JSON metadata.
- **Expanded Local View (radius 12)**:
  `local_view` is a 25×25 binary occupancy grid (625 cells), sized so 8-tile pits on `platforming-9` / `platforming-10` are visible before jump commitment without the full noise of radius 14. Goals remain in `global_state` only.
- **Configurable Network Widths**:
  `local_feature_dim`, `lstm_hidden_size`, and `mlp_hidden_dim` live in `intelligence/config.toml` and are overridable via CLI / Optuna.

### B. Client CLI & Optuna Tuning (`tune.py`)
- Expanded Optuna search space in `client/src/cli/commands/tune.py` to tune:
  `tile_exploration_reward`, `wall_hugging_reward`, `goal_distance_reward_scale`, `turn_reward`, `jump_reward`, `finished_reward`, `learning_rate`, and `entropy_regularization`.
- **Sequential mastery objective**: each trial uses a blank `{agent}_trial_{n}`, trains `platforming-1`→`10` with weight inheritance, then play-evals with `--eval-runs` (default **15**). Optuna maximizes **mean of the `tail_k` lowest per-level WRs** (default 3); promotion requires **`min` ≥ `--mastery-threshold`** (0.8). Always log min / mean / per-level table.
- **Retention for mastery**: tune wires review `E`/`R`/`K` (default `E=1500`), projected focus-slot accounting, post-curriculum consolidation (`platforming-6,7,9`), and lexicographic Optuna ranking.
- `--tune-architecture` is a **second-pass** flag only.
- `train` emits `level_mastery` JSON events after each single-level focus/play phase.

### C. Docker Infrastructure
- Clean release build with **0 compiler warnings**.
- Detached `run-ai-dev.sh` by default with higher mem/shm defaults for long Optuna runs.
- Environment file `.env` configures `TRAIN_ARGS=serve --host 0.0.0.0 --port 8001`.
- Server API active and healthy on `http://localhost:8001/init`.

---

## 3. Pending Questions — Status

| Item | Status |
| :--- | :--- |
| Q1 Sequential mastery Optuna scoring | **Done** — tail-k Optuna score + min promotion gate; see `tune.py` + [Engine Protocol](../agentic_fine_tuning/engine_protocol.md) |
| Q2 Vision + NN architecture liberty | **Done** — radius 12 local view; architecture CLI / second-pass `--tune-architecture` |
| Q3 Documentation sync | **Done** — protocol, roadmap, commands, this handoff |
| Q4 Pack mastery under retention | **Done** — Phase 7; promoted Trial 1 defaults (`min`/`mean` WR = 1.0); see [Fine-Tuning History](fine_tuning_history.md) |
| Q5 Jump cleanliness vs discovery | **Open** — Stage B polish design; see [Jump Cleanliness Polish](jump_polish_stage_b.md) |

### Next agent action
1. Stage A mastery defaults are promoted — do **not** re-litigate Pass 1 discovery by hardening `jump_reward` alone.
2. Discuss / implement **Stage B** jump polish per [jump_polish_stage_b.md](jump_polish_stage_b.md): mastery lock + minimize play jump rate (instrumentation first).
3. Pass 2 `--tune-architecture` only if polish cannot hold mastery.
4. Do **not** promote from diluted averages or from cleaner-but-below-threshold jump trials.
