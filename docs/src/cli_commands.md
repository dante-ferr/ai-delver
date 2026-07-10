# CLI Commands Reference

All commands live in `client/src/cli/commands/` and are routed via `client/src/cli/main.py`.

---

## Commands

### `train`
Runs a full training session by submitting a training request to the intelligence server and streaming trajectory replays over a WebSocket.

> [!NOTE]
> For a deep dive into parameter constraints, structured JSON stdout log formats, and signal handling for training orchestration, see the [CLI Training Client](cli_training_client.md) documentation page.

```bash
poetry run python src/cli/main.py train \
    --levels "Ai Test #1" \
    --cycles 10 \
    --episodes-per-cycle 32 \
    --mode static \
    --agent ppo_delver
```

#### Optional Parameters and Hyperparameter Overrides
You can optionally configure checkpoints or override individual training and reward parameters from `config.toml` for the duration of the training session:
* `--checkpoint-interval <int>`: Frequency (in cycles) to save intermediate checkpoints under `data/agents/<agent_name>/checkpoints/cycle_<N>.zip` (default `0`, which disables periodic saving).
* `--checkpoint <name_or_number>`: Name or cycle number of an existing checkpoint to load from the checkpoints directory for warm-starting training.
* `--learning-rate <float>`: Learning rate for the policy optimizer.
* `--gamma <float>`: Discount factor for rewards.
* `--entropy-regularization <float>`: Policy entropy weight to control exploration.
* `--not-finished-reward <float>`: Penalty given for failing to finish.
* `--finished-reward <float>`: Reward given for reaching the goal.
* `--turn-reward <float>`: Reward/penalty given on directional turns.
* `--frame-step-reward <float>`: Reward/penalty given per frame step (time penalty).
* `--tile-exploration-reward <float>`: Reward given per unique tile explored.
* `--jump-reward <float>`: Penalty given per jump.
* `--wall-hugging-reward <float>`: Penalty given for touching walls.
* `--goal-distance-reward-scale <float>`: Scaling multiplier for the goal-distance reward.

#### Dynamic Parameter Mapping Mechanism
The CLI and the intelligence server employ a dynamic mapping pattern to transfer parameters without maintaining duplicate lists of variable names across different architectural layers (CLI arguments $\rightarrow$ Client payload $\rightarrow$ Server request $\rightarrow$ Core config):

1. **Client-Side Filtering**:
   In `client/src/cli/commands/train.py`, the CLI separates session control arguments and client-side parameters from hyperparameter overrides by checking parsed inputs against a set of `standard_keys` (e.g., `levels`, `mode`, `agent`, etc.). Anything else is dynamically gathered into a `config_overrides` dictionary:
   ```python
   standard_keys = {"levels", "cycles", "episodes_per_cycle", "mode", "agent", "server", "command", "checkpoint"}
   config_overrides = {
       key: val for key, val in vars(args).items()
       if key not in standard_keys and val is not None
   }
   ```
2. **REST API Payload**:
   The `config_overrides` dictionary is sent as an optional property in the `TrainRequest` JSON body submitted to the server's `/train` endpoint.
3. **Server-Side Application**:
   Upon session initialization, the intelligence server invokes `config.update_config(request.config_overrides)`. This resets the server configuration state to the defaults specified in `config.toml`, applies the active overrides (including `checkpoint_interval`), and triggers the recalculation of reward scaling factors and collector step counts.

**GUI Trigger**: The "Train" button in `_train_buttons_container.py`.

---

### `stats`
Reads the agent's local `metadata.json` and trajectory files, calculates aggregate statistics, and outputs them as a `stats` JSON event.

```bash
poetry run python src/cli/main.py stats --agent ppo_delver
```

**GUI Trigger**: The "Get stats" button in `trajectory_stats_panel.py`.

---

### `interrupt`
Sends an HTTP `POST` to the intelligence server to interrupt an active training session by its session ID.

```bash
poetry run python src/cli/main.py interrupt \
    --session-id <uuid> \
    --server localhost:8001
```

**GUI Trigger**: The "Interrupt Training" button in `_train_buttons_container.py`.

---

### `create-agent`
Creates a new agent on disk with a default name.

```bash
poetry run python src/cli/main.py create-agent --name "Brave Delver"
```

**GUI Trigger**: CLI command only, or implicit during startup/reset.

---

### `save-agent`
Saves/persists the agent state on disk under the agent's name directory.

```bash
poetry run python src/cli/main.py save-agent --name "Brave Delver"
```

**GUI Trigger**: The "Save" icon button in `_agent_save_button.py`.

---

### `load-agent`
Loads an existing agent from a specified path directory on disk.

```bash
poetry run python src/cli/main.py load-agent --path "data/agents/Brave Delver"
```

**GUI Trigger**: The "Load" folder button in `_agent_load_button.py` via `_AgentLoaderOverlay`.

---

### `tune`
Runs a developer-only automated hyperparameter tuning session using Optuna. It suggests parameters (learning rate, entropy regularization, finished reward) across multiple trials, runs the training script as a subprocess, prunes bad trials early if the loss diverges, and reports the best parameter set upon completion.

```bash
poetry run python src/cli/main.py tune \
    --levels "Ai Test #1" \
    --cycles 5 \
    --episodes-per-cycle 32 \
    --agent ppo_delver \
    --trials 10
```

**GUI Trigger**: Developer CLI command only.

---


## Output and Event Formats

The GUI runs the CLI as a subprocess (using `subprocess.Popen`) with `stdout=subprocess.PIPE`. It reads lines from stdout in real-time on a background thread and parses each line as a JSON event:

```python
for line in iter(self.train_process.stdout.readline, ""):
    data = json.loads(line)
    event = data.get("event")
    if event == "session_created":
        training_state_manager.set_value("training", True)
    elif event == "progress":
        ...
    elif event == "metrics":
        training_state_manager.update_nerd_metrics(...)
```

### Event Types

| Event | Source Command | Description |
|:---|:---|:---|
| `info` | `train` | Informational messages (e.g. batch-size adjustment) |
| `init_started` | `train` | Levels are being prepared |
| `request_sent` | `train` | Training request sent to server |
| `session_created` | `train` | Server accepted and registered the session |
| `progress` | `train` | A cycle completed (includes cycle number and episode count) |
| `level_transition` | `train` | Agent graduated to a new level |
| `metrics` | `train` | Deep learning metrics snapshot (loss, average return, step, episodes) |
| `checkpoint` | `train` | Intermediate model weights checkpoint received from server |
| `completed` | `train` | All cycles finished successfully |
| `interrupted` | `train` | Training was interrupted gracefully |
| `stats` | `stats` | Aggregate statistics for the agent |
| `agent_created` | `create-agent` | Emitted when a new agent is successfully created |
| `agent_saved` | `save-agent` | Emitted when an agent's state is successfully saved |
| `agent_loaded` | `load-agent` | Emitted when an agent is successfully loaded |
| `error` | any | An unrecoverable error occurred |

### `metrics` Event (Nerd Stats)
The `metrics` event is emitted at each `LOG_INTERVAL` steps during training. It carries:
```json
{
  "event": "metrics",
  "step": 500,
  "loss": 0.042183,
  "average_return": -1.2345,
  "episodes": 64
}
```
The GUI's `TrainingStateManager.update_nerd_metrics()` appends these to running history lists and notifies any open `NerdStatsWindow` via its registered listener callback.
