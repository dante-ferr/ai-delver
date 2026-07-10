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

## 2. Server-Client Model Weight Transfer (Completed)

We have fully implemented and verified bi-directional network weight transfer between the client CLI and the training server:

1. **Downstream (Server $\rightarrow$ Client)**:
   * When training completes (either normally or via interrupt), the uvicorn server serializes the final model policy, base64-encodes the zip archive, and streams it to the CLI client over the active WebSocket connection.
   * The client decodes and saves it locally at `data/agents/<agent_name>/model_weights.zip`.
2. **Upstream (Client $\rightarrow$ Server)**:
   * When training is initialized, the client checks for the existence of `model_weights.zip`. If present, it base64-encodes the archive and attaches it to the `/train` request payload.
   * The server extracts and decodes the model weights, mapping variables dynamically by name and shape to warm-start both the actor and value networks.
   * Resets Keras global session state before training runs to avoid global layer name counter collisions.

---

## 3. Agent Checkpoint Versioning & Snapshotting

Once bidirectional weight transfer is implemented, we can easily snapshot different versions of the agent:

* **Tagging Runs**: Allow saving checkpoints at custom cycle counts or milestones (e.g., `data/agents/<agent_name>/snapshots/epoch_50.keras`).
* **Evaluation & Rollbacks**: An agent or developer can load a specific checkpoint to evaluate victory rates, compare learning curves of different snapshots side-by-side, or rollback a run if performance starts diverging or collapsing.
