# GUI-to-CLI Integration Protocol

All interactive GUI buttons in AI Delver that trigger server-side operations **must call the CLI** (`src/cli/main.py`) as a subprocess rather than talking to the FastAPI server directly.

This is a deliberate architectural decision: the CLI is the single source of truth for all training orchestration logic. Routing GUI interactions through the CLI prevents duplicating complex state-management, error handling, batch-size validation, and level-saving logic inside the GUI code.

---

## The Rule

> **Every GUI button that triggers a training lifecycle action must call `src/cli/main.py` as a subprocess, not the intelligence API directly.**

This means:
- The GUI **never** calls `httpx` or `websockets` directly to the intelligence server for training-related flows.
- All training operations (`train`, `stats`, `interrupt`) are exposed via the CLI and invoked using `sys.executable`.
- The GUI reads structured JSON lines from the CLI's `stdout` to update state and the UI.

---

## Why This Matters

| Concern | Without the Protocol | With the Protocol |
|:---|:---|:---|
| **Logic Duplication** | GUI and CLI each duplicate batch-size validation, level-hashing, and session wiring | CLI owns all orchestration logic; GUI just reads JSON stdout |
| **Boilerplate** | Every GUI action requires implementing async WebSocket/HTTP client code inside Tkinter threads | GUI is a thin subprocess runner + JSON parser |
| **Testability** | GUI logic is hard to test in isolation | CLI commands can be run and tested headlessly |
| **Extensibility** | Adding a new feature requires updating both GUI and CLI separately | Feature is added to the CLI first; GUI gets it for free |

---

## Current CLI Commands

All commands live in `client/src/cli/commands/` and are routed via `client/src/cli/main.py`.

### `train`
Runs a full training session by submitting a training request to the intelligence server and streaming trajectory replays over a WebSocket.

```bash
poetry run python src/cli/main.py train \
    --levels "Ai Test #1" \
    --cycles 10 \
    --episodes-per-cycle 32 \
    --mode static \
    --agent ppo_delver
```

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

## How the GUI Reads CLI Output

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
| `completed` | `train` | All cycles finished successfully |
| `interrupted` | `train` | Training was interrupted gracefully |
| `stats` | `stats` | Aggregate statistics for the agent |
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

---

## Adding a New CLI Command

1. Create `client/src/cli/commands/<name>.py` with a `run_<name>(args)` entry point.
2. Register the subparser in `client/src/cli/main.py`.
3. If the command needs a GUI button, add the button to the appropriate panel, and have it launch the CLI command via `subprocess.Popen(sys.executable, "src/cli/main.py", "<name>", ...)`.
4. Parse the JSON events from stdout and update `StateManager` as needed.
5. Document the new event types in this file.
