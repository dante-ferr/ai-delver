# Physics Engine Performance & Optimizations

This document explains the performance profiling, bottlenecks, and optimization work performed on the **AI Delver** physics engine integration, culminating in the pure-Rust trainer under `intelligence/`.

---

## 1. Summary of Optimizations & Performance Impact

Under a parallel training workload of **38 environments** on **Ai Test #3**, we observed the following durations and throughput.

**Device notes (important):**
- Historical Python / early Rust columns: environments always ran on **CPU**. The Python TF-Agents stack **auto-used the GPU for PPO** when TensorFlow saw a CUDA device; the original doc labeled the suite “(pure CPU),” which is ambiguous for ML-enabled rows.
- **Pure Rust (CPU PPO)**: Rayon collect on CPU + libtorch PPO on CPU.
- **Pure Rust (CUDA PPO)**: Rayon collect on CPU + libtorch PPO on **CUDA** (`device = auto` / `--device cuda`, RTX 3050).

Equal-frame ML-enabled comparisons use **~22,800 env-steps** (12× 50-step collect windows). ML-disabled / collect FPS is from stepping time only (`--no-learning` or `collect_fps`).

| Metric | Python Engine (bbf4486) | Rust Engine (Optimized / Threads) | Pure Rust CPU PPO | Pure Rust CUDA PPO |
| :--- | :---: | :---: | :---: | :---: |
| **Device (physics / PPO)** | **CPU / GPU (typical)** | **CPU / GPU (typical)** | **CPU / CPU** | **CPU / CUDA** |
| **Startup Overhead** | **2.05s** | **~0.1s** | **~0.25s** | **~0.25s** |
| **Active Run (ML Enabled)** | **22.33s** | **30.29s** | **~24.3s** (collect **2.33s** + update **22.0s**) | **~9.3s** (collect **1.33s** + update **7.94s**) |
| **Active Run (ML Disabled)** | **9.62s** | **15.94s** | **~0.52s** (scaled; **~44k collect FPS**) | same collect path |
| **Average FPS (ML Enabled)** | **849.9** | **624.4** | **923 overall** / **~10.6k collect** | **~2288 overall** / **~19.6k collect** |
| **Average FPS (ML Disabled)** | **1959.8** | **1184.4** | **~43.8k collect** | **~43.8k collect** |
| **Total Duration (ML Enabled)** | **31.48s** | **37.83s** | **24.70s** | **9.96s** |

Relative to the optimized Python+Rust baseline (**37.83s** ML-on): Rust **CPU** PPO is already ~**1.5×** faster; Rust **CUDA** PPO is ~**3.8×** faster on the same equal-frame workload. Simulation collect alone is ~**37×** the old ML-disabled FPS.

---

## 2. Key Architecture Optimizations

### A. Thread-Pool Integration (`BatchedPyEnvironment`)
* **Problem**: PyO3 and the Rust runtime are not safe to use after a process `fork` (leading to allocator crashes and thread pool deadlocks). Therefore, TF-Agents' `ParallelPyEnvironment` had to use the `spawn` multiprocessing start method. Spawning 38 parallel Python processes sequentially on CPU took **105 seconds** because each subprocess had to start an independent interpreter and import TensorFlow.
* **Solution**: Transitioned the environment manager to **`BatchedPyEnvironment`**, which runs all environments on Python threads in the same process. This eliminates the process startup/shutdown overhead and avoids the slow `spawn` initialization path entirely.

### B. Releasing the GIL in Rust (`py.allow_threads`)
* **Problem**: Python threads run sequentially due to the Global Interpreter Lock (GIL), which prevents concurrent execution of physics updates even when multi-threaded.
* **Solution**: Modified the Rust `step()` function in `physics_engine.rs` to take a PyO3 `Python` reference and wrap the Rapier2D simulation ticks inside a `py.allow_threads` block:
  ```rust
  py.allow_threads(|| {
      // Rapier2D physics calculations run here in parallel across threads
  });
  ```
  This allows all 38 environments to run their physics updates concurrently on different CPU cores.

### C. Pure-Rust Trainer (`intelligence/`)
* **Problem**: Even with GIL release and threaded envs, Python still owned the PPO loop, observation assembly, and TensorFlow graph — capping end-to-end throughput and keeping PyO3 crossings on every step.
* **Solution**: Moved collection, reward, actor-critic, and PPO into a native binary. Environments step with **Rayon**; learning uses **`tch`/libtorch**. Physics-only profiling uses `--no-learning` (random actions, no gradient updates).
* **PPO fixes that recovered training speed** (after an initial ~80s equal-frame ML-on regression on CPU):
  1. Rollout horizon aligned to `collect_seconds_per_env` (**50** steps/env), matching the old Python collect window instead of full **600**-step episodes.
  2. Recurrent minibatch sizing uses ceiling math so multiple envs pack into each BPTT update (was collapsing to **1 env** when `steps > minibatch_size`).
  3. Metrics split **`collect_s` / `collect_fps`** from **`update_s`** so physics wins are not masked by optimizer time.
* **CUDA**: Default `device = "auto"` selects CUDA when a CUDA-enabled libtorch build can see a GPU. Build with `TORCH_CUDA_VERSION=cu126` (or `cu118` / `cu128`) and `--features tch/download-libtorch`. The trainer force-loads `libtorch_cuda` at startup because GNU ld `--as-needed` otherwise drops it and PyTorch reports no GPU.

---

## 3. Minimizing PyO3 Boundary Crossing Overhead (State Caching)

### The PyO3 Boundary Problem
Every time Python reads a property (like position or velocity) of a physics object, it calls a PyO3 method (e.g. `get_delver()`), which clones the Rust struct and converts it to a PyO3 object. 
In a single frame step, the environment, reward calculator, and observation builders access these properties multiple times. With 38 parallel environments, this leads to **570+ boundary crossings per frame step**, adding a high serialization/deserialization bottleneck.

### Caching and Scalability
A common question is: **Will caching still be viable when we have many dynamic objects?**
* **Yes! Caching is actually the most scalable solution.**
* **Why?** The physical state of any dynamic object (position, velocity, status) **only changes during the physics step** (`physics_engine.step(dt)`). Between physics steps, the states are completely frozen/immutable.
* **How it scales**: Instead of querying each dynamic object individually from Python throughout the step, Rust can return the **entire unified frame state** (containing all dynamic entities) in a single Python object returned by `step()`.
* **Crossings**: This ensures that regardless of the number of dynamic objects (10, 100, or 1000) or how many times their positions are queried in Python, the PyO3 boundary is only crossed **exactly once per frame step**. All queries in Python memory are answered instantly from the cached state.

In the pure-Rust trainer this boundary no longer exists on the training hot path: observation and reward logic run against native `runtime_core` state in-process.
