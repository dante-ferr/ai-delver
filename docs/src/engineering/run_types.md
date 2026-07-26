# Run Types & Policy Execution Modes

> Didactic intro: [Seeing what it learned](../intelligence/seeing_what_it_learned.md).

AI Delver categorizes episode executions into three distinct **run types** (execution modes). Each mode serves a specific operational purpose in the training and evaluation pipeline, differing in action selection strategy, data streaming, and learning behavior.

---

## Summary Comparison Matrix

| Run Type                | Action Selection           | Learning / Gradient Updates | Frame Streaming to GUI        | Replay / Path Visualizer | Primary Purpose                         |
| ----------------------- | -------------------------- | --------------------------- | ----------------------------- | ------------------------ | --------------------------------------- |
| **1. Training Collect** | Stochastic (`multinomial`) | **Yes** (PPO updates)       | No (metrics only)             | No                       | Experience gathering for PPO rollouts   |
| **2. Showcase**         | Deterministic (`argmax`)   | No (during evaluation pass) | **Yes** (`EpisodeTrajectory`) | **Yes**                  | Progress snapshot at cycle end          |
| **3. Play Mode**        | Deterministic (`argmax`)   | **No** (`no_learning`)      | **Yes** (`EpisodeTrajectory`) | **Yes**                  | Single-shot evaluation without training |

---

## 1. Training Collect Runs (Stochastic / Exploration)

- **Purpose**: Collect rollout buffers across parallel environments to compute Generalized Advantage Estimation (GAE) and update policy network weights.
- **Action Selection**: **Stochastic**. Actions are sampled randomly from the network's output probability distribution using categorical sampling (`multinomial(1, true)` in `intelligence/src/agent/model.rs`).
- **Exploration Mechanism**: Influenced by `entropy_regularization` in `config.toml`. High entropy regularization forces the action probabilities to stay uniform, driving active exploration.
- **Data Flow**: To save network bandwidth, raw step-by-step frame snapshots are **not** streamed to the client. Instead, aggregated cycle metrics (loss, reward mean, victory rate) are emitted as `metrics` events.

---

## 2. Showcase Runs (Deterministic Evaluation / Replay)

- **Purpose**: Evaluate the agent's current policy deterministically at the end of each training cycle and stream the trajectory to the GUI for visual playback.
- **Action Selection**: **100% Deterministic (Greedy)**. Executed via `run_showcase` in `intelligence/src/trainer/showcase.rs` using `greedy_action` (`argmax` in `intelligence/src/agent/model.rs`).
- **Runtime Exploration**: **None**. Showcase runs do not sample randomly or explore at runtime. The policy selects whichever action has the single highest logit (`argmax`) at each state.
- **Data Flow**: Captures continuous entity positions, velocities, actions, and states into an `EpisodeTrajectory` JSON payload. This is streamed to the client via WebSockets as a `showcase` event and rendered in the **GUI Replay Viewer** and **Path Visualizer**.
- **Automatic reviews**: During a review-pass session, showcases for **review** levels are still computed on the server (and may appear in the progress stream), but the CLI does **not** persist them to the agent's trajectory folder. Only focus / coach leftover showcases are registered for the trajectory viewer. See [Automatic Reviews](../player/automatic_reviews.md).

---

## 3. Play Mode Runs (`--play` Evaluation)

- **Purpose**: Execute a single evaluation pass of an agent's current weights on a chosen level without training, applying gradient updates, or mutating curriculum state.
- **Action Selection**: **100% Deterministic (Greedy)**.
- **Relationship to Showcase**: Technically identical to Showcase Runs under the hood—both invoke `run_showcase`. The difference is operational: Showcase runs execute automatically in the background at cycle boundaries during training, while Play Mode runs are triggered on-demand via the CLI `--play` flag or user request.

---

## 4. Exploration vs. Weight Drift

A common point of confusion is why a Showcase run might show degraded or jumping behavior after a previous Showcase run demonstrated an optimal jumpless path.

- **Runtime Exploration**: Takes place **only during Training Collect Runs** via stochastic sampling. Showcase runs do not perform runtime exploration.
- **Weight Drift**: Takes place **between Showcase runs** as a result of training updates.
- **Showcase is not “best ever”**: each showcase re-runs argmax on **current** weights. It does not freeze or replay the historically best trajectory.

```text
[Showcase #1]
Network Weights State A  --->  On flat ground: logit(Run) > logit(Jump)
Argmax selects RUN       --->  Showcase #1 is jumpless & optimal!

      │
      ▼  (Training Cycle: 1000s of stochastic steps collected across env_batch_size environments)
      │  (PPO updates network weights based on collected rollouts)
      │

[Showcase #2]
Network Weights State B  --->  On flat ground: logit(Jump) > logit(Run)
Argmax selects JUMP      --->  Showcase #2 shows jumping behavior!
```

### Why Decision Boundaries Shift

If the reward penalty for jumping (`jump_reward`) is small relative to the goal completion reward (`finished_reward`), training rollouts that include jumps receive nearly identical high rewards as jumpless rollouts. After `reward_scale()` (≈ `finished_reward`), a finish alone is ~1.00 normalized — a few takeoffs barely move the UI’s two-decimal reward.

During training updates, PPO updates the shared feature extractor and LSTM weights. If `entropy_regularization` is high, the action heads are pushed toward uniform probabilities. As a result, the network's internal decision boundary can shift so that `logit(Jump)` exceeds `logit(Run)` at certain states. When the next Showcase run executes `argmax`, it deterministically follows this new, degraded decision boundary.

### Goal Rehearsal Lock + post-clear jump anneal (mitigation)

When enabled (`goal_rehearsal_lock` in `config.toml`), each cycle runs a greedy showcase plus stochastic **scouts**, locks the fewest-takeoff victory (confidence tie-break), and behavioral-clones it into PPO (`goal_rehearsal_epochs`). Training collect stays stochastic; the lock pulls argmax back toward the neat win.

Separately, after a level’s first clear this train session, effective `jump_reward` anneals from discovery-band toward `jump_reward_polish` over `jump_anneal_cycles`. **`turn_reward` is not annealed** (mazes need cheap turns). See [Stage B](jump_polish_stage_b.md).
