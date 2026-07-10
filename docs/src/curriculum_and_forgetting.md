# Curriculum & Forgetting Prevention

To train a reinforcement learning agent to handle complex layouts (platforming, traps, combat), AI Delver employs a **Player-Driven Curriculum** with **Automated Forgetting Prevention** safety nets.

---

## 1. Player-Driven Curriculum (AI Coaching)

Instead of employing a fully automated curriculum on the server, AI Delver implements a gamified manual curriculum. The player acts as the "AI Coach," directing the agent's progress:

1. **Sequential Skill Acquisition**: The player trains the agent on Level 1 to master basic platforming.
2. **Skill Transfer (Warm-Starts)**: Once platforming is solid, the player selects Level 2 (e.g. traps) and starts training. The client automatically uploads the agent's existing weights (`model_weights.zip`) to the server to warm-start Level 2.
3. **Save State Rollbacks**: If training on a level goes poorly, the player can use checkpoints (`cycle_<N>.zip`) as save states to roll back and try different coaching parameters.

---

## 2. The Challenge of Catastrophic Forgetting

In sequential task training, reinforcement learning agents suffer from **catastrophic forgetting**—modifying neural pathways to adapt to new environments (hazards) while overwriting the pathways used for older skills (precise platforming).

To manage this, the system incorporates two defensive strategies:

### A. Level Mixing (Multi-Task Combo Levels)
To cement multiple skills together, the player should train the agent on combo levels that feature both challenges (e.g. platforming *and* traps). This forces the weights to optimize against both distributions simultaneously.

### B. Adaptive Learning Rate Scaling
When transferring an agent to a new level layout, modifying weights too aggressively will erase existing skills. To shield learned weights, the system automatically dials down the learning rate, allowing the agent to adapt to new elements with minimal disruption to old knowledge.

---

## 3. Automated Forgetting Prevention System

To make the coaching experience smooth and prevent accidental skill wipes, the client CLI automatically manages forgetting prevention:

1. **Curriculum Tracking**: The client tracks the agent's training history in `data/agents/<agent_name>/trajectories/metadata.json` under the `trained_levels` list.
2. **Challenge Detection**: When starting a training session, the CLI compares the target levels with the historical `trained_levels` list.
3. **Automatic Scaling**:
   * If the agent is warm-starting AND facing a new level (not in the trained history):
     * The system automatically scales the default learning rate down to `0.000075` (1/4 of the default `0.0003` value).
     * If the user has explicitly overridden the learning rate in their arguments, the CLI respects their override and logs the choice.
4. **History Consolidation**: Upon successful training completion, the new levels are appended to `metadata.json`'s `trained_levels` list.
