# CLI Training Client

AI Delver includes a standalone command-line executable (`train_cli.py`) under `client/src/cli/` to run training sessions headlessly. 

This client communicates with the local or remote FastAPI intelligence server, validates levels, verifies batch constraints, and streams trajectory progress.

---

## 1. Execution

To execute the CLI client, run the script from the `client/` directory using Poetry:

```bash
poetry run python src/cli/train_cli.py \
    --levels "Ai Test #1" \
    --episodes-per-cycle 32 \
    --mode static \
    --cycles 10 \
    --agent ppo_delver \
    --server localhost:8001
```

---

## 2. Command Line Arguments

| Parameter | Required | Type | Description |
| :--- | :---: | :---: | :--- |
| `--levels` | Yes | `str` | A comma-separated list of level names (e.g. `"Level1,Level2"`). |
| `--episodes-per-cycle` | Yes | `int` | Number of episodes collected in each training cycle. |
| `--mode` | Yes | `str` | Transition mode: `static` (fixed cycles limit) or `dynamic` (runs until graduation). |
| `--cycles` | No | `int` | The number of training cycles (only applicable in `static` mode). |
| `--agent` | Yes | `str` | Name of the agent subdirectory where training level saves and outputs are recorded. |
| `--server` | No | `str` | Address and port of the training API (defaults to `localhost:8001`). |

---

## 3. Server Constraints Validation

On startup, the CLI automatically queries the server's `/init` endpoint to fetch the `env_batch_size` (the number of parallel execution environments). 

*   Since episodes are collected in batches, `--episodes-per-cycle` must be a multiple of the server's batch size.
*   If the user-provided value is not a multiple, the CLI automatically rounds it to the nearest multiple of `env_batch_size` (with a floor of `env_batch_size`) and outputs an `info` event line.

---

## 4. Structured JSON Logs (Stdout)

The CLI outputs all logs to standard output (`stdout`) as JSON lines. This makes it extremely easy for a parent GUI application (e.g. our Python client application) or CI/CD pipelines to monitor progress programmatically.

### Example Events

#### `info`
Emitted for informational logging (like constraint adjustments):
```json
{"event": "info", "message": "Adjusted episodes-per-cycle from 50 to 64 to align with env_batch_size (32) constraints."}
```

#### `init_started`
Emitted when levels are being validated and hashed:
```json
{"event": "init_started", "message": "Preparing levels and verifying configuration..."}
```

#### `request_sent`
Emitted when submitting the training session initialization request to the server:
```json
{"event": "request_sent", "message": "Sending training request to http://localhost:8001/train..."}
```

#### `session_created`
Emitted when the server successfully registers the training session:
```json
{"event": "session_created", "session_id": "f88278a0-c66b-4d5e-bbc1-09425fcf7692", "message": "Training session started successfully."}
```

#### `progress`
Emitted when a training cycle completes:
```json
{"event": "progress", "cycle": 1, "level_episode_count": 64, "message": "Completed cycle 1"}
```

#### `level_transition`
Emitted when graduating or moving to the next level in the queue:
```json
{"event": "level_transition", "levels_trained": 1, "message": "Transitioned to next level."}
```

#### `completed`
Emitted when all levels and cycles finish successfully:
```json
{"event": "completed", "duration": "45.20s", "message": "Training completed successfully."}
```

#### `error`
Emitted when an error terminates execution:
```json
{"event": "error", "message": "Failed to connect to training server: Connection refused."}
```

---

## 5. Signal Handling and Interruption

The CLI handles system signals (`SIGINT` / `SIGTERM`) gracefully:
*   If a terminal user presses `Ctrl+C` or a process runner signals the subprocess, the client catches the interrupt.
*   It sends an HTTP POST request to the server's `/interrupt-training/{session_id}` endpoint to signal the backend to pause, save, and exit.
*   Once finished, it outputs `{"event": "interrupted", "message": "..."}` and exits cleanly with exit code `0`.
