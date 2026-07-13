# Intelligence (Rust-only)

Training lives in `intelligence_rs/`. Shared hyperparameters are in
`src/ai/config.toml`.

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

See `intelligence_rs/README.md` for local `cargo` usage.
