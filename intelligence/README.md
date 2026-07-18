# Intelligence (Rust PPO trainer + training server)

Native PPO training for AI Delver. The binary has two modes:

- **`serve`** — long-lived HTTP/WebSocket API on port `8001` (what the GUI/client expect).
- **`train`** — one-shot CLI run for benchmarks and headless jobs.

It reuses:

- `ai-delver-level` for validated level loading.
- `runtime_core` for the same Rapier simulation used by the Python runtime.
- `tch`/libtorch for the recurrent actor-critic and PPO updates.

Hyperparameters live in [`config.toml`](config.toml).

## Container (training server)

From the repository root:

```bash
make build-ai-dev
make run-ai-dev
```

This starts:

```text
ai-delver-intelligence serve --host 0.0.0.0 --port 8001
```

and publishes `localhost:8001`. The GUI’s “Connect now” / `GET /init` should succeed while the container stays up.

One-shot train inside the same image (exits when done):

```bash
./run-ai-dev.sh --train-args='train --levels "Ai Test #3" --cycles 1 --episodes-per-cycle 38 --no-learning'
```

## API surface (compat with client)

| Endpoint | Role |
| :--- | :--- |
| `GET /init` | Health + `env_batch_size` / `max_training_levels` |
| `POST /train` | Start a session from level JSON; returns `session_id` |
| `POST /interrupt-training/{session_id}` | Cooperative cancel |
| `WS /episode-trajectory/{session_id}` | Metrics, progress showcase stubs, checkpoints, weights |

## Local prerequisites

Install libtorch **2.7.x** matching `tch 0.20`, or use the download feature.

### CPU build

```bash
cargo build --release \
  --manifest-path intelligence/Cargo.toml \
  --features tch/download-libtorch
```

### CUDA build (recommended for training)

```bash
export TORCH_CUDA_VERSION=cu126
cargo build --release \
  --manifest-path intelligence/Cargo.toml \
  --features tch/download-libtorch
```

`device = "auto"` (default) selects CUDA when the GPU is visible.

## Train (CLI)

```bash
cargo run --release \
  --manifest-path intelligence/Cargo.toml \
  --features tch/download-libtorch -- \
  train \
  --levels "Ai Test #1" \
  --cycles 10 \
  --runs-per-cycle 5 \
  --agent ppo_delver
```

`--runs-per-cycle` is preferred (full-length run equivalents). The trainer converts runs to collect-window episode slots using `max_seconds_per_episode / collect_seconds_per_env`. Legacy `--episodes-per-cycle` still works.
## Serve (CLI)

```bash
cargo run --release \
  --manifest-path intelligence/Cargo.toml \
  --features tch/download-libtorch -- \
  serve --host 127.0.0.1 --port 8001
```

## Current limitations

- Dynamic curriculum mode still errors; use static.
- WebSocket showcase frames advance the client cycle counter but do **not** yet stream full episode trajectories for replay.
- `model_bytes_b64` warm-start expects libtorch `.ot` bytes. Legacy TF-Agents zip payloads are ignored with a log line.
