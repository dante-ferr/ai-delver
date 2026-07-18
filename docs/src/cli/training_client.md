# CLI Training Client Internals

How the headless training path talks to the intelligence server: batch constraints, JSON stdout events, signals, and weight sync.

**Command flags and the full event table:** [Commands Reference](commands.md).  
**Entrypoint:** `client/src/cli/main.py` (not the legacy `train_cli.py` name in older notes).

```bash
cd client
poetry run python src/cli/main.py train \
    --levels "Ai Test #1" \
    --runs-per-cycle 5 \
    --mode static \
    --cycles 10 \
    --agent ppo_delver \
    --server localhost:8001
```

Prefer `--runs-per-cycle`. Legacy `--episodes-per-cycle` remains for low-level / Optuna use.

---

## 1. Server constraints validation

On startup, the CLI queries `/init` for `env_batch_size`.

* Episodes are collected in batches, so `--episodes-per-cycle` must be a multiple of `env_batch_size`.
* If not, the CLI rounds to the nearest multiple (floor `env_batch_size`) and emits an `info` event.

---

## 2. Structured JSON logs (stdout)

All lifecycle logs are JSON lines on `stdout` for the GUI / CI.

### Example events

#### `info`
```json
{"event": "info", "message": "Adjusted episodes-per-cycle from 50 to 64 to align with env_batch_size (32) constraints."}
```

#### `init_started`
```json
{"event": "init_started", "message": "Preparing levels and verifying configuration..."}
```

#### `request_sent`
```json
{"event": "request_sent", "message": "Sending training request to http://localhost:8001/train..."}
```

#### `session_created`
```json
{"event": "session_created", "session_id": "f88278a0-c66b-4d5e-bbc1-09425fcf7692", "message": "Training session started successfully."}
```

#### `progress`
```json
{"event": "progress", "cycle": 1, "level_episode_count": 64, "message": "Completed cycle 1"}
```

#### `level_transition`
```json
{"event": "level_transition", "levels_trained": 1, "message": "Transitioned to next level."}
```

#### `completed`
```json
{"event": "completed", "duration": "45.20s", "message": "Training completed successfully."}
```

#### `error`
```json
{"event": "error", "message": "Failed to connect to training server: Connection refused."}
```

Full event catalog: [Commands Reference — Output and Event Formats](commands.md#output-and-event-formats).

---

## 3. Signal handling and interruption

* `SIGINT` / `SIGTERM` → HTTP POST `/interrupt-training/{session_id}`.
* Then emit `interrupted` and exit `0`.

Also available as `main.py interrupt --session-id …`.

---

## 4. Client–server weights synchronization (warm-starts)

1. **Upload:** if `data/agents/{agent}/model_weights.zip` (or current `.ot` payload) exists, attach to `/train`.
2. **Download:** on complete/interrupt, server pushes weights over the WebSocket; client writes them back under the agent folder.

GUI must not reimplement this — [GUI-to-CLI Protocol](gui_protocol.md).
