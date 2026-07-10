# Roadmap & Future Plans

This document outlines the short-to-medium term plans for expanding the AI Delver training loop, focusing on agent fine-tuning, state management, and weight persistence.

---

## 1. Configurable Training Parameters & TOML Format

The deep learning and reinforcement learning hyperparameters are managed by `intelligence/src/ai/config.toml`.

### TOML Format Advantage
We have migrated the configuration from `config.json` to `config.toml` (using `tomllib` with a Python <3.11 fallback to `tomli`).
* **Why**: TOML supports native comments (`#`). In Reinforcement Learning, hyperparameter decisions (e.g., why `entropy_regularization` is `0.2` or why `wall_hugging_reward` is negative) are highly empirical. Having inline comments allows developers and AI orchestrators to document changes and understand tuning logic.

### Parameters to Expose
We intend to make these parameters fully configurable via the CLI (and eventually GUI knobs) so that an orchestrating AI agent can automatically tune the policy:

| Parameter | Type | Default | Description |
| :--- | :---: | :---: | :--- |
| `learning_rate` | `float` | `0.0003` | Step size for gradient descent weight updates. |
| `gamma` | `float` | `0.995` | Discount factor for future rewards (balancing short-term vs long-term goals). |
| `entropy_regularization`| `float` | `0.2` | Penalty/incentive for policy entropy (higher values promote exploration). |
| `tile_exploration_reward`| `float`| `0.04` | Positive reward given to the agent for exploring new grid coordinates. |
| `finished_reward` | `float` | `100.0` | Sparse positive reward awarded only upon successfully solving the level. |
| `wall_hugging_reward` | `float` | `-0.2` | Negative penalty to discourage the agent from sticking to walls. |

---

## 2. Server-Client Model Weight Transfer

Currently, the intelligence server and the client run in separate environments, and the agent's neural network weights are only stored in the memory of the training server process. If the server or the GUI restarts, training progress is lost.

### The Next Step: Bidirectional Weight Sync
We plan to implement a protocol to sync model weights (`.keras` / `.h5` or PyTorch state dicts) over the network:

1. **Downstream (Server $\rightarrow$ Client)**:
   * When training completes or is interrupted, the intelligence server serializes the model weights.
   * The server sends the weights payload (as raw bytes or via a structured endpoint/WebSocket frame) to the CLI training client.
   * The CLI client saves the weights file under the agent's local directory: `data/agents/<agent_name>/model_weights.keras`.
2. **Upstream (Client $\rightarrow$ Server)**:
   * When starting a training session for an existing agent, the CLI client reads the local `model_weights.keras` file.
   * The client transmits the weights to the server during the session initialization (`/train` or WebSockets).
   * The server loads the weights into the neural network before starting the training loop (warm-starting).

---

## 3. Agent Checkpoint Versioning & Snapshotting

Once bidirectional weight transfer is implemented, we can easily snapshot different versions of the agent:

* **Tagging Runs**: Allow saving checkpoints at custom cycle counts or milestones (e.g., `data/agents/<agent_name>/snapshots/epoch_50.keras`).
* **Evaluation & Rollbacks**: An agent or developer can load a specific checkpoint to evaluate victory rates, compare learning curves of different snapshots side-by-side, or rollback a run if performance starts diverging or collapsing.
