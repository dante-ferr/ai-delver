# Intelligence (Rust PPO trainer)

Native PPO training for AI Delver. The trainer reuses:

- `ai-delver-level` for validated level loading.
- `runtime_core` for the same Rapier simulation used by the Python runtime.
- `tch`/libtorch for the recurrent actor-critic and PPO updates.

Hyperparameters live in [`config.toml`](config.toml).

## Container

From the repository root:

```bash
make build-ai-dev
make run-ai-dev
```

Or from this directory:

```bash
make build
make run
```

Override trainer CLI flags:

```bash
./run-ai-dev.sh --build --train-args='--levels "Ai Test #3" --cycles 1 --episodes-per-cycle 38 --no-learning'
```

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
# Example: CUDA 12.6 libs. Other supported tags for tch 0.20 / torch 2.7: cu118, cu126, cu128.
export TORCH_CUDA_VERSION=cu126
cargo build --release \
  --manifest-path intelligence/Cargo.toml \
  --features tch/download-libtorch

# Point the dynamic loader at the downloaded libtorch (path under target/*/build/torch-sys-*/out/...).
export LD_LIBRARY_PATH="$(find intelligence/target* -path '*/libtorch/lib/libtorch.so' | head -1 | xargs dirname):${LD_LIBRARY_PATH}"
```

`device = "auto"` (default) selects CUDA when the GPU is visible. The binary also
force-loads `libtorch_cuda` at startup so GNU ld `--as-needed` cannot hide CUDA.

Or point at a Python CUDA PyTorch install:

```bash
export LIBTORCH_USE_PYTORCH=1
export LIBTORCH_BYPASS_VERSION_CHECK=1   # if the wheel patch version differs slightly
```

See the [`tch-rs` setup documentation](https://github.com/LaurentMazare/tch-rs) for
custom `LIBTORCH` directories.

## Build and test

```bash
cargo build --release --manifest-path intelligence/Cargo.toml
cargo test --manifest-path intelligence/Cargo.toml
```

For a source-only compile check on a machine without libtorch:

```bash
cargo check \
  --manifest-path intelligence/Cargo.toml \
  --features tch/doc-only
```

## Train

```bash
cargo run --release \
  --manifest-path intelligence/Cargo.toml \
  --features tch/download-libtorch -- \
  --levels "Ai Test #1" \
  --cycles 10 \
  --episodes-per-cycle 38 \
  --agent ppo_delver
```

Physics-only profiling:

```bash
cargo run --release \
  --manifest-path intelligence/Cargo.toml \
  --features tch/download-libtorch -- \
  --levels "Ai Test #3" \
  --cycles 1 \
  --episodes-per-cycle 38 \
  --no-learning
```

Level names resolve through `client/data/level_saves`. Protocol events are
emitted as one JSON object per stdout line.

## Current limitation

Static training and checkpoint loading/saving are implemented. Dynamic
curriculum mode exits with a clear error rather than silently behaving as
static training.
