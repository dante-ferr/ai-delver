# Training Server Gap After the Rust Migration

This note explains the cutover from the Python FastAPI training server to the Rust stack, and the **Option A** façade that restores a long-lived API for the GUI/client.

---

## Historical symptom

After `99abe42` (Rust trainer cutover):

1. `make run-ai-dev` ran a one-shot `cargo run … train` and exited.
2. Compose no longer published `8001:8001`.
3. The GUI’s [`ServerConnectionPanel`](../../client/src/app/pages/agent/_server_connection_panel.py) showed **“Training server is not connected”** because `GET http://localhost:8001/init` failed.

That was not a Docker attach bug — nothing was listening on port 8001.

---

## What changed (timeline)

| Era | Commit / work | What `make run-ai-dev` started | Lifetime |
| :--- | :--- | :--- | :--- |
| **Before** | pre-`99abe42` | Python `src/main.py` → **uvicorn FastAPI** on `:8001` | Stays up; waits for client requests |
| **Gap** | `99abe42` | One-shot Rust CLI train | Exits when training finishes |
| **Now** | Option A façade | Rust `serve --host 0.0.0.0 --port 8001` | Stays up; accepts `/init`, `/train`, … |

The [Rust-only training plan](rust_only_training_plan.md) scoped work to simulation + PPO. The HTTP/WebSocket layer was omitted until this façade.

---

## Architecture

### Target (Option A — current direction)

```text
GUI ──subprocess──► client CLI (train / interrupt)
                         │
                         │ HTTP + WebSocket
                         ▼
              Rust axum server (:8001)   ← `serve`
                         │
                         ▼
              Rust PPO trainer (spawn_blocking session)
```

One-shot benchmarks still use the `train` subcommand (Docker via `--train-args='train …'`).

### Client contract

Still implemented by [`TrainingClient`](../../client/src/client_requests/training_client.py):

| Endpoint | Role | Façade status |
| :--- | :--- | :--- |
| `GET /init` | Health + env batch / max levels | Done |
| `POST /train` | Start session; return `session_id` | Done (static mode) |
| `POST /interrupt-training/{session_id}` | Cooperative cancel | Done |
| `WS /episode-trajectory/{session_id}` | Stream events | Metrics + showcase trajectories (actions + frame snapshots) + weights |

GUI rule unchanged: buttons go through the [GUI→CLI protocol](gui_cli_protocol.md).

---

## Remaining gaps

1. **Showcase trajectories** — each cycle runs a greedy episode and streams an `EpisodeTrajectory` with `delver_actions` and `frame_snapshots` (`entity_id: "delver"`). Replay applies poses via a Delver position override (live play still reads physics).
2. **Weight format** — warm-start / download uses libtorch `.ot` bytes in `model_bytes_b64`. Legacy TF-Agents zip payloads are ignored with a log line; the client still saves as `model_weights.zip` by name.
3. **Dynamic curriculum** — still rejected; use static mode.
4. **Multi-session GPU contention** — sessions can be created concurrently; only one should train on a single GPU in practice (serialize or queue later if needed).
5. **Collect vs episode stats** — cycle metrics may show `episodes: 0` when the collect horizon is shorter than `max_seconds_per_episode` and the agent never finishes; showcase still records one eval episode per cycle.
6. **Server logs** — serve mode prints short human lines; full trajectory JSON is not dumped to stdout (still sent on the WebSocket).

---

## How to run

```bash
make run-ai-dev          # serve on localhost:8001 (container stays up)
make run-client-dev      # GUI; Connect now → GET /init
```

Headless one-shot:

```bash
make run-ai-dev ARGS='--train-args=train --levels "Ai Test #1" --cycles 1 --episodes-per-cycle 38 --agent ppo_delver'
```

---

## Related docs

- [Rust-Only Reinforcement Learning Pipeline](rust_only_training_plan.md)
- [GUI-to-CLI Integration Protocol](gui_cli_protocol.md)
- [CLI Training Client](cli_training_client.md)
- [Intelligence README](../../intelligence/README.md)
