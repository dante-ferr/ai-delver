# Physics Engine Performance & Optimizations

This document explains the performance profiling, bottlenecks, and optimization work performed on the **AI Delver** physics engine integration.

---

## 1. Summary of Optimizations & Performance Impact

Under a parallel training workload of **38 environments** on **Ai Test #3** (pure CPU), we observed the following durations and throughput:

| Metric | Python Engine (bbf4486) | Rust Engine (Initial / Spawn) | Rust Engine (Optimized / Threads) | Overall Speedup (vs Initial Rust) |
| :--- | :---: | :---: | :---: | :---: |
| **Startup Overhead** | **2.05s** | **105.00s** | **~0.1s** | **1050x faster** |
| **Shutdown Overhead** | **~9.0s** | **~65.0s** | **~5.1s** | **12.7x faster** |
| **Active Run (ML Enabled)** | **22.33s** | **36.28s** | **30.29s** | **16.5% faster** |
| **Active Run (ML Disabled)** | **9.62s** | **19.16s** | **15.94s** | **16.8% faster** |
| **Average FPS (ML Enabled)** | **849.9 FPS** | **523.0 FPS** | **624.4 FPS** | **19.4% higher** |
| **Average FPS (ML Disabled)** | **1959.8 FPS** | **985.9 FPS** | **1184.4 FPS** | **20.1% higher** |
| **Total Duration (ML Enabled)** | **31.48s** | **190.60s** | **37.83s** | **5.0x faster** |

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
