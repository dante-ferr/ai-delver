# Senses & actions

At every discrete control tick the Delver gets an observation and chooses a small discrete action.

## Local view (vision)

Defined in `intelligence/src/environments/observation.rs`:

- **Radius 12** → side length `2×12+1 = 25` → **`LOCAL_VIEW_CELLS = 625`**.
- Each cell is occupancy (solid vs empty) in a window centered on the Delver.
- Sized so **8-tile pits** are visible *before* the jump commit.
- **Goals are not painted into the grid** — that would leak “where to go” as a painted beacon. Relative goal lives in `global_state`.

Think of it as a coarse “fog of war” occupancy map: enough geometry to invent gap jumps, not a full-level cheat sheet.

## Global state (proprioception + goal)

**`GLOBAL_STATE_SIZE = 7`**: compact floats for body/intent cues and relative goal information (see `level_env` when building the observation). This is the “inner ear + compass,” not a second camera.

## Action space

Two categorical heads (see `ActorCritic` in `agent/model.rs`):

| Head | Choices | Meaning |
| :--- | :--- | :--- |
| **Run** | 3 | Left / idle / right (encoded as indices; CLI trajectories map to signed run) |
| **Jump** | 2 | Hold-jump pressed or not (hold through ascent for full height; early release = short hop) |

Physics still owns coyote time, impulse, gravity, and jump-cut on release. RL only chooses *intent* at `actions_per_second` (default 10 Hz).

## Takeoff vs held jump

Reward and neatness metrics care about **takeoff impulses**, not every air frame while Jump is held.

The env marks `jump_takeoff` when Jump is pressed *and* vertical velocity increases from the impulse (see `level_env`). That prevents “hold Jump across a gap” from looking like dozens of jumps.

**Variable height:** takeoff is rising-edge only. Holding Jump after takeoff preserves upward velocity; releasing while `vy > 0` multiplies `vy` by `jump_cut_multiplier` (short hop). Gap / rise authoring budgets assume a **full hold**.

Next: [Rewards](rewards.md).
