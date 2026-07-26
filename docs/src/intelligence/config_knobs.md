# Config knobs

Authoritative file: `intelligence/config.toml` (unknown keys rejected). CLI / API can override many fields for `train` / `tune`.

## When you are coaching a player Delver

Usually leave defaults alone. Coaching changes **weights**, not engine constants.

## When you are improving the engine

| Goal | Touch first | Avoid first |
| :--- | :--- | :--- |
| Invent skills / clear new packs | Discovery rewards, entropy, LR | Forever-harsh static jump tax |
| Keep clears neat after invent | Lock + anneal knobs | Banning actions |
| Capacity / lagging mid-pack | Pass 2 `--tune-architecture` | Random width thrash every trial |
| Retention across curriculum | Review E/R/K, consolidate levels | Raising finish only |

## Discovery band (invent)

- `tile_exploration_reward`
- `jump_reward` (mild)
- `entropy_regularization`
- `goal_distance_reward_scale`
- `learning_rate`

Lean **exploratory** here now that polish is scheduled — see [Engine Protocol](../agentic_fine_tuning/engine_protocol.md) § Stage B stance.

## Polish band (after clear)

- `jump_reward_polish`, `jump_anneal_cycles`
- `goal_rehearsal_*`

## Mastery / finish

- `finished_reward`, `not_finished_reward`
- `frame_step_reward`

## Maze-safe

- `turn_reward` — keep discovery-safe; **do not** post-clear anneal it for jump neatness.

## Network / PPO plumbing

- `env_batch_size`, `collect_seconds_per_env`, `actions_per_second`
- `ppo_num_epochs`, `minibatch_size`, `gae_lambda`, `clip_epsilon`, …
- `local_feature_dim`, `lstm_hidden_size`, `mlp_hidden_dim`

Promoted numeric baseline: [Fine-Tuning History §8](../engineering/fine_tuning_history.md#8-promoted-baseline-engine-configuration).

Next: [Scalability](scalability.md).
