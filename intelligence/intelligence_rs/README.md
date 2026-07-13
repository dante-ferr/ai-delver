# Rust-only trainer

Native PPO training for AI Delver. The trainer reuses:

- `ai-delver-level` for validated level loading.
- `runtime_core` for the same Rapier simulation used by the Python runtime.
- `tch`/libtorch for the recurrent actor-critic and PPO updates.

No Python process or PyO3 boundary is used while training.

## Prerequisites

Install libtorch **2.7.x** matching `tch 0.20`, or use the download feature.

### CPU build

```bash
cargo build --release \
  --manifest-path intelligence/intelligence_rs/Cargo.toml \
  --features tch/download-libtorch
```

### CUDA build (recommended for training)

```bash
# Example: CUDA 12.6 libs. Other supported tags for tch 0.20 / torch 2.7: cu118, cu126, cu128.
export TORCH_CUDA_VERSION=cu126
cargo build --release \
  --manifest-path intelligence/intelligence_rs/Cargo.toml \
  --features tch/download-libtorch

# Point the dynamic loader at the downloaded libtorch (path under target/*/build/torch-sys-*/out/...).
export LD_LIBRARY_PATH="$(find intelligence/intelligence_rs/target* -path '*/libtorch/lib/libtorch.so' | head -1 | xargs dirname):${LD_LIBRARY_PATH}"
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
cargo build --release --manifest-path intelligence/intelligence_rs/Cargo.toml
cargo test --manifest-path intelligence/intelligence_rs/Cargo.toml
```

For a source-only compile check on a machine without libtorch:

```bash
cargo check \
  --manifest-path intelligence/intelligence_rs/Cargo.toml \
  --features tch/doc-only
```

## Train

`device = "auto"` in `config.toml` (default) selects CUDA when the linked
libtorch was built with CUDA and a GPU is visible; otherwise it falls back to
CPU. Override with `--device cuda` or `--device cpu`.

Run from the repository root:

```bash
cargo run --release \
  --manifest-path intelligence/intelligence_rs/Cargo.toml \
  --features tch/download-libtorch -- \
  --levels "Ai Test #1" \
  --cycles 10 \
  --episodes-per-cycle 38 \
  --agent ppo_delver
```

Physics-only profiling (random actions, no PPO updates):

```bash
cargo run --release \
  --manifest-path intelligence/intelligence_rs/Cargo.toml \
  --features tch/download-libtorch -- \
  --levels "Ai Test #3" \
  --cycles 1 \
  --episodes-per-cycle 38 \
  --no-learning
```

Level names resolve through `client/data/level_saves`; direct paths are also
accepted. Protocol events are emitted as one JSON object per stdout line.
Diagnostics go to stderr.

The default batch contains 38 environments stepped with Rayon. Configuration
comes from `intelligence/src/ai/config.toml`, with CLI arguments taking
precedence. Pass `--no-learning` to force profiling mode regardless of the
`no_learning` value in `config.toml`.

## Current limitation

Static training and checkpoint loading/saving are implemented. Dynamic
curriculum mode exits with a clear error rather than silently behaving as
static training.
