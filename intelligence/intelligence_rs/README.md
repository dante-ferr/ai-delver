# Rust-only trainer

Native PPO training for AI Delver. The trainer reuses:

- `ai-delver-level` for validated level loading.
- `runtime_core` for the same Rapier simulation used by the Python runtime.
- `tch`/libtorch for the recurrent actor-critic and PPO updates.

No Python process or PyO3 boundary is used while training.

## Prerequisites

Install libtorch, or install a compatible Python PyTorch distribution and set:

```bash
export LIBTORCH_USE_PYTORCH=1
```

The libtorch version must match the version expected by `tch 0.20`. See the
[`tch-rs` setup documentation](https://github.com/LaurentMazare/tch-rs) if a
custom `LIBTORCH` directory or CUDA build is required.

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

Run from the repository root:

```bash
cargo run --release \
  --manifest-path intelligence/intelligence_rs/Cargo.toml -- \
  --levels "Ai Test #1" \
  --cycles 10 \
  --episodes-per-cycle 38 \
  --agent ppo_delver
```

Level names resolve through `client/data/level_saves`; direct paths are also
accepted. Protocol events are emitted as one JSON object per stdout line.
Diagnostics go to stderr.

The default batch contains 38 environments stepped with Rayon. Configuration
comes from `intelligence/src/ai/config.toml`, with CLI arguments taking
precedence.

## Current limitation

Static training and checkpoint loading/saving are implemented. Dynamic
curriculum mode exits with a clear error rather than silently behaving as
static training.
