# Technical Specification: Rust-Only Reinforcement Learning Pipeline

This document defines the technical specification, design pattern, and execution plan to transition the entire reinforcement learning pipeline (simulation, collection, and PPO training) to a 100% pure Rust executable. 

This plan serves as the handover document for the next agent to execute.

---

## 1. Context & Performance Baseline

We recently converted the physics runtime of **AI Delver** to Rust (using Rapier2D). In the initial integration with Python (`TF-Agents`):
1. **Startup Overhead**: Due to PyO3 fork safety limitations, we had to spawn 38 parallel Python processes. Sequentially importing TensorFlow on CPU took **105 seconds**.
2. **IPC & GIL Bottleneck**: Serialization/deserialization between Python processes and GIL contention on threads throttled the simulation throughput.
3. **Optimized Baseline**: By switching to `BatchedPyEnvironment` (threading) and releasing the GIL in PyO3 (`py.allow_threads`), we achieved **37.83s total duration** (5.0x speedup) and **624.4 active FPS** (ML enabled).

To reach **5,000 to 10,000+ active FPS**, we are migrating the high-level PPO training loop, neural networks, and environment coordination fully to Rust, bypassing Python completely.

---

## 2. Design Goal: Clean Architecture

The user has explicitly requested a **clean architecture** mirroring the current Python `intelligence` setup. The Rust implementation must avoid spaghetti code and enforce clean separation of concerns.

### Python Architecture to Mirror

```
intelligence/src/
├── ai/
│   ├── agents/            # Agent definition and hyperparameter factories
│   ├── environments/      # Environment wrappers, observation builders, reward calculators
│   └── trainer/           # Training cycle loop and batch management
└── cli/                   # CLI runner and stdout JSON logging
```

### Proposed Rust Architecture (`intelligence_rs/src/`)

```
src/
├── main.rs                # Entry point, CLI parser (using clap)
├── cli/                   # Handles stdout logging of JSON lines for GUI updates
├── environments/
│   ├── mod.rs
│   ├── level_env.rs       # Observation dict, grid conversions, step/reset loops
│   ├── reward.rs          # Dijkstra-based dense reward calculator
│   └── exploration.rs     # Exploration occupancy grid tracking
├── agent/
│   ├── mod.rs
│   ├── ppo.rs             # GAE calculator, PPO clipped surrogate loss, optimization steps
│   └── model.rs           # ActorCritic networks, preprocessing (local_view + global_state), LSTMs
└── trainer/
    ├── mod.rs
    └── loop.rs            # Coordinates collection cycles and epoch updates
```

---

## 3. Technology Stack

1. **Deep Learning**: **`tch-rs`** (Rust bindings for PyTorch's C++ library, `libtorch`).
   - *Why*: Libtorch provides fully optimized C++ tensor computations, Autograd, and GPU/CPU optimizers. This prevents us from writing deep learning code from scratch.
2. **Parallelization**: **`rayon`** (data-parallelism thread pool).
   - *Why*: Rayon lets us step 38 environments concurrently with $O(1)$ scaling and zero GIL/IPC overhead.
3. **CLI & Serialization**: **`clap`** (arguments) and **`serde_json`** (GUI event protocol).

---

## 4. Hyperparameter Invalidation Notice

> [!IMPORTANT]
> During codebase review, we discovered why the current Python TF-Agents PPO policy is not learning:
> - In `ppo_agent_factory.py`, the `entropy_regularization` parameter is set to **`0.2`**.
> - An entropy coeff of `0.2` is extremely high, forcing the policy to remain random and preventing convergence.
> - **In the Rust PPO implementation, set the default `entropy_coef` to a standard value (e.g., `0.01` or `0.001`)** to ensure convergence.

---

## 5. Implementation Roadmap for the Next Agent

### Step 1: Initialize the Rust Crate
1. Create a new Rust project (e.g. `intelligence_rs` or adding it as a binary in the existing workspace).
2. Configure `Cargo.toml` with dependencies: `tch`, `rayon`, `serde`, `serde_json`, `clap`, and the project's local physics/level libraries.

### Step 2: Implement the Environment Wrapper (`environments/`)
1. Re-implement the `DijkstraGrid` and `ExplorationGrid` logic in Rust.
2. Build the `LevelEnvironment` wrapper around `RustPhysicsEngine`.
3. Construct the observation tensor dictionary:
   - `local_view`: 15x15 cropped platforms grid.
   - `global_state`: normalized goal vector, velocity, grid offsets, and ground flag.

### Step 3: Implement Actor-Critic Models (`agent/model.rs`)
Using `tch::nn`, define the actor-critic neural network:
1. Preprocessing networks for `local_view` (Flatten + Linear) and `global_state` (LayerNorm + Linear).
2. Concatenation layer.
3. Recurrent LSTM block (128 units).
4. Policy head (categorical actions: 3-class run, 2-class jump) and Value head (scalar value).

### Step 4: Implement PPO Optimization (`agent/ppo.rs`)
1. Implement the collection buffer.
2. Compute Generalized Advantage Estimations (GAE) and target returns.
3. Implement the PPO clipped loss:
   $$L^{CLIP}(\theta) = \hat{\mathbb{E}}_t \left[ \min(r_t(\theta)\hat{A}_t, \text{clip}(r_t(\theta), 1-\epsilon, 1+\epsilon)\hat{A}_t) \right]$$
4. Execute backpropagation steps using PyTorch's Adam optimizer.

### Step 5: Implement GUI Event Output (`cli/`)
To maintain complete compatibility with the Python GUI client:
1. Ensure the Rust binary accepts arguments matching the current Python trainer.
2. Print progress updates to `stdout` as JSON lines, matching:
   `{"event": "progress", "cycle": 1, "level_episode_count": 32, "message": "Completed cycle 1"}`
   `{"event": "metrics", "step": 20, "loss": -0.337, ...}`
