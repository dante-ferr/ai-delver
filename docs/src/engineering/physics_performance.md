# Physics Engine Performance & Optimizations

Historical record of the performance work that moved AI Delver from a Python/TF-Agents training loop over a Rust Rapier runtime to a fully native trainer under `intelligence/`.

Benchmark workload unless noted: **38** parallel environments on **Ai Test #3**, equal-frame ML-enabled runs at **~22,800** env-steps (12 × 50-step collect windows). Collect FPS is stepping throughput only (`--no-learning` / `collect_fps`).

---

## 1. Results

| Metric | Python + Rust runtime (bbf4486) | Rust runtime + threaded Python (optimized) | Pure Rust trainer (CPU PPO) | Pure Rust trainer (CUDA PPO) |
| :--- | :---: | :---: | :---: | :---: |
| **Physics / PPO devices** | CPU / GPU (TF when available) | CPU / GPU (TF when available) | CPU / CPU | CPU / CUDA |
| **Startup** | 2.05s | ~0.1s | ~0.25s | ~0.25s |
| **Shutdown** | ~9.0s | ~5.1s | ~0.15s | ~0.15s |
| **Active run (ML on)** | 22.33s | 30.29s | ~24.3s (collect 2.33s + update 22.0s) | ~9.3s (collect 1.33s + update 7.94s) |
| **Active run (ML off)** | 9.62s | 15.94s | ~0.52s (~44k collect FPS) | same collect path |
| **FPS (ML on)** | 849.9 | 624.4 | 923 overall / ~10.6k collect | ~2288 overall / ~19.6k collect |
| **FPS (ML off)** | 1959.8 | 1184.4 | ~43.8k collect | ~43.8k collect |
| **Total (ML on)** | 31.48s | 37.83s | 24.70s | 9.96s |

Versus the optimized Python+Rust baseline (37.83s ML-on): native CPU PPO was ~1.5× faster end-to-end; native CUDA PPO ~3.8× faster. Collect-only throughput rose ~37× over the old ML-off FPS.

Early Rust+Python spawn-based runs (not tabulated above) paid ~105s startup and ~65s shutdown from process spawn + TensorFlow import; switching to in-process threaded envs removed that overhead before the pure-Rust trainer existed.

---

## 2. What changed

### Threaded environments instead of spawn
PyO3/Rapier are not safe after `fork`, so `ParallelPyEnvironment` had to use `spawn`. Starting 38 interpreters and importing TensorFlow on CPU cost ~105s. Moving to `BatchedPyEnvironment` kept all envs in one process on Python threads and eliminated that startup path.

### GIL release in Rapier steps
Threaded Python still serialized on the GIL during physics. Wrapping Rapier ticks in `py.allow_threads` let the 38 envs advance concurrently on CPU cores.

### Pure-Rust trainer
Python still owned PPO, observations, and TensorFlow, so PyO3 crossings and interpreter overhead remained. The `intelligence/` binary now owns collection, reward, actor-critic, and PPO: Rayon for env steps, `tch`/libtorch for learning. Notable training-path fixes:

1. Collect horizon uses `collect_seconds_per_env` (50 steps), matching the old Python window instead of full 600-step episodes.
2. Recurrent minibatches pack multiple envs (ceiling math); earlier integer division collapsed to one env per update when `steps > minibatch_size`.
3. Metrics report `collect_s` / `collect_fps` separately from `update_s`.
4. `device = "auto"` prefers CUDA; libtorch CUDA is force-loaded at startup because GNU ld `--as-needed` otherwise drops `libtorch_cuda`.

### PyO3 state caching (Python era)
While Python still drove the loop, each property read cloned Rust state across the FFI. Caching a full frame state from `step()` cut that to one crossing per frame. The native trainer no longer crosses PyO3 on the hot path; observation and reward read `runtime_core` in-process.
