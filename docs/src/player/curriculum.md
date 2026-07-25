# Curriculum & Forgetting Prevention

To train a reinforcement learning agent to handle complex layouts (platforming, traps, combat), AI Delver employs a **Player-Driven Curriculum** with **Automated Forgetting Prevention** safety nets. That coaching loop is the **player’s** job.

Developers / agentic AIs that tune the **training engine** should read [Agentic Fine-Tuning](../agentic_fine_tuning/index.md) (skill ladder + eval pack formula). That does not replace this player coaching loop; dependence of traps/puzzles on platforming applies to both.

---

## 1. Player-Driven Curriculum (AI Coaching)

Instead of employing a fully automated curriculum on the server, AI Delver implements a gamified manual curriculum. The player acts as the "AI Coach," directing the agent's progress:

1. **Sequential Skill Acquisition**: The player trains the agent on Level 1 to master basic platforming.
2. **Skill Transfer (Warm-Starts)**: Once platforming is solid, the player selects Level 2 (e.g. traps) and starts training. The client automatically uploads the agent's existing weights (`model_weights.zip`) to the server to warm-start Level 2.
3. **Save State Rollbacks**: If training on a level goes poorly, the player can roll the Delver back to a checkpoint from the agent panel’s restore table (columns: level, date, cycle, kind). Before each training session, the client auto-saves a `pre_level` checkpoint of the current weights for every selected level. Mid-run checkpoints are also written every N cycles (configured in the train panel) and tagged with the active level and timestamp.

---

## 2. The Challenge of Catastrophic Forgetting

In sequential task training, reinforcement learning agents suffer from **catastrophic forgetting**—modifying neural pathways to adapt to new environments (hazards) while overwriting the pathways used for older skills (precise platforming).

To manage this, the system incorporates three defensive strategies:

### A. Level Mixing (Multi-Task Combo Levels)
To cement multiple skills together, the player should train the agent on combo levels that feature both challenges (e.g. platforming *and* traps). This forces the weights to optimize against both distributions simultaneously.

### B. Adaptive Learning Rate Scaling
When transferring an agent to a new level layout, modifying weights too aggressively will erase existing skills. To shield learned weights, the system automatically dials down the learning rate, allowing the agent to adapt to new elements with minimal disruption to old knowledge.

### C. Automatic Review Passes
After enough focus training (measured in episodes), the client inserts review-pass sessions that replay previously trained levels. Full explanation (cadence, static mix, showcases vs collect): [Automatic Reviews](automatic_reviews.md).

---

## 3. Automated Forgetting Prevention System

To make the coaching experience smooth and prevent accidental skill wipes, the client CLI automatically manages forgetting prevention:

1. **Curriculum Tracking**: The client tracks the agent's training history in `data/agents/<agent_name>/trajectories/metadata.json` under the `trained_levels` list (plus `level_hashes` and `review_state`).
2. **Challenge Detection**: When starting a focus training session, the CLI compares the coach-selected levels with the historical `trained_levels` list.
3. **Automatic Scaling**:
   * If the agent is warm-starting AND facing a new level (not in the trained history):
     * The system automatically scales the default learning rate down to `0.000075` (1/4 of the default `0.0003` value).
     * If the user has explicitly overridden the learning rate in their arguments, the CLI respects their override and logs the choice.
4. **History Consolidation**: When new model weights are written from the server (`model_weights` WebSocket event), the session levels are merged into `trained_levels` and review state is updated ([Automatic Reviews](automatic_reviews.md)). Interrupted sessions that still deliver weights commit the same way.

---

## 4. Agent Starting Modes: Blank Slate vs. Pre-Trained Foundation

To give the player full agency over the coaching experience, the application offers two starting modes when creating a new agent:

### A. Blank Slate Mode (Starting from Scratch)
*   **Concept**: The agent is initialized with completely randomized weights.
*   **Player Experience**: The player builds custom training arenas and watches the agent learn to navigate from absolute zero.
*   **Why it works**: Because the application ships with **auto-tuned hyperparameter defaults** (`config.toml`), the fresh agent trains stably and quickly without diverging, making the initial learning loop engaging and satisfying.

### B. Pre-Trained Foundation Mode (Warm-Start Shipped Weights)
*   **Concept**: The agent is initialized with a copy of the developer's pre-trained model weights (e.g. `default_weights.zip`).
*   **Player Experience**: The agent starts with basic motor skills (walking, jumping, hazard evasion) already mastered. The player can immediately jump into training the agent on advanced, specialized custom tasks.

---

## 5. Automatic Reviews

See **[Automatic Reviews](automatic_reviews.md)** for the full cadence, static-mix vs showcase clarification, and worked examples.

Summary:

* Arms after ~**8000 focus episodes** (`E`), scheduling at most **`K=5`** priors with ~**`R=100`** episode slots each (review-only mix; budgeted cycles).
* One Train click can **auto-chain** focus → review when `E` is crossed (dual GUI progress bars).
* Curriculum updates only after `model_weights` are written.
* Review-level showcase trajectories are **not persisted** on the client; coach/focus showcases still save as usual.

---

## 6. Checkpoint Bundles (Weights + Curriculum)

Checkpoints under `data/agents/<agent>/checkpoints/` are **bundles**:

```text
checkpoints/<uuid>/
  model_weights.ot
  curriculum.json
manifest.json
```

`curriculum.json` snapshots `trained_levels`, `level_hashes`, and `review_state` from the **committed** curriculum at save time (pre-session for `pre_level` / mid-run `interval` checkpoints). Restoring a checkpoint copies weights onto `model_weights.zip` **and** restores those curriculum fields so policy and review state stay aligned.

Legacy single-file `cycle_*.zip` / flat `{uuid}.zip` checkpoints still resolve for weights-only restore (curriculum left unchanged, with no bundle metadata).

