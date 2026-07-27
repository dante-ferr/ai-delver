# Training cycle (start to finish)

Everything important happens in `trainer::train` (`trainer/loop.rs`). One **cycle** is one full turn of the outer loop.

```mermaid
flowchart TD
  start["Cycle N begins"] --> annealCfg["Build envs with annealed jump+explore"]
  annealCfg --> collect["Collect rollouts: stochastic acts × env_batch"]
  collect --> ppo["PPO update"]
  ppo --> metrics["Emit metrics / progress"]
  metrics --> greedy["Greedy showcase per level"]
  greedy --> clear["If victory → mark level cleared"]
  clear --> scouts["K stochastic scouts"]
  scouts --> lock["Maybe update Goal Rehearsal Lock"]
  lock --> tick["Advance anneal clocks for cleared levels"]
  tick --> bc["BC rehearse all locked trajs"]
  bc --> ckpt["Optional checkpoint"]
  ckpt --> next["Cycle N+1"]
```

## 1. Effective jump + explore + entropy for this cycle

For each level hash:

- Never cleared this `/train` call → discovery `jump_reward` / `tile_exploration_reward`.
- Cleared → interpolate toward polish targets over the matching anneal cycle spans.

Envs are rebuilt every cycle so collect feels the schedule. A new `/train` (coach moves to another level) resets clear/anneal state for that session.

Entropy is **session-wide**: discovery until every coach level has cleared, then anneal toward polish (slowest level’s clock). Scout budget switches to `goal_rehearsal_scout_episodes_polish` per level once that level has cleared.

If the **greedy** showcase fails after a clear, that level’s clear/anneal state is **reset** to discovery — otherwise cold polish recreates the idle/left spawn local min after an unlearn.

## 2. Collect

- `env_batch_size` parallel `LevelEnvironment`s.
- Each rollout window lasts `collect_seconds_per_env × actions_per_second` steps.
- Actions: stochastic policy (unless `no_learning`).
- Episodes that finish mid-window reset in place; victories/timeouts counted for metrics.

## 3. PPO update

One `ppo.update(rollout)` (or more rollouts if `episodes_per_cycle` needs several windows). Emits loss / entropy / reward_mean on a `metrics` event.

## 4. Greedy showcase

For each level in the train set, `run_showcase` (argmax) builds a GUI trajectory and reports `jump_takeoffs`, `victorious`, `policy_confidence`.

First victory → `clear_progress` entry (anneal starts after this cycle’s tick).

## 5. Stochastic scouts

If `goal_rehearsal_lock`, run **K** `run_scout` episodes (multinomial). Pre-clear `K = goal_rehearsal_scout_episodes`; after that level clears, `K = goal_rehearsal_scout_episodes_polish` (hunt cleaner 0-hop locks harder).

## 6. Lock update

Among victorious greedy + scout trajectories, keep the one with:

1. Strictly fewer takeoffs, or
2. Equal takeoffs and higher `policy_confidence`.

Store obs/action tensors as `RehearsalTrajectory`.

## 7. Anneal clock + BC

- Every cleared level’s “cycles since clear” increments once per cycle.
- Each locked traj is `ppo.rehearse(..., goal_rehearsal_epochs)`.

Then the next cycle collects again — now under a slightly harsher jump cost if the level has cleared, and with a policy already tugged toward the locked path.

## Intuition for “learned on cycle 1”

If prior weights already almost solve the map, one collect+update plus a victorious showcase can lock a clean traj immediately. Discovery band J lets the inventing happen; lock+anneal keeps the win neat afterward.

Next: [Seeing what it learned](seeing_what_it_learned.md).
