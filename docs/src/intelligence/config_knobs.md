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
| Retention across curriculum | Review E/R/K in `client/src/config.toml`, consolidate levels | Raising finish only |

## Discovery band (invent)

- `tile_exploration_reward` — strong enough to beat **idle/left spawn local min**. Do not drop discovery back to Trial-5 `0.0165` without compensating entropy. **Anneal** explore after clear (`tile_exploration_reward_polish`) — leaving it hot is the main neatness delay.
- `jump_reward` (mild)
- `entropy_regularization` — discovery band (e.g. `~0.06`); anneals to polish after clear. Static `0.2` historically blocked convergence.
- `goal_distance_reward_scale`
- `learning_rate`

Lean **exploratory** here now that polish is scheduled — see [Engine Protocol](../agentic_fine_tuning/engine_protocol.md) § Stage B stance.

## Polish band (after clear)

- `tile_exploration_reward_polish`, `explore_anneal_cycles`
- `jump_reward_polish`, `jump_anneal_cycles`
- `entropy_regularization_polish`, `entropy_anneal_cycles`
- `polish_fail_grace` (hold polish through N greedy misses before discovery reset)
- `goal_rehearsal_scout_episodes_polish` (more scouts after clear)
- `goal_rehearsal_epochs` / lock enable / `goal_rehearsal_mirror_clone`
- Post-clear: mirror at `mirror_augmentation_prob_polish`; jitter/dropout off (not full augs-off)

## Mastery / finish

- `finished_reward`, `not_finished_reward`
- `frame_step_reward`
- Early-stop (`--early-stop`): `early_stop_victory_streak`, `early_stop_min_cycles`,
  `early_stop_plateau_window`, `early_stop_plateau_eps` — raise streak / min cycles / window
  (or lower eps) if focus levels stop before teachings are strong enough.

## Maze-safe

- `turn_reward` — keep discovery-safe; **do not** post-clear anneal it for jump neatness.

## Network / PPO plumbing

- `env_batch_size`, `collect_seconds_per_env`, `actions_per_second`
- `ppo_num_epochs`, `minibatch_size`, `gae_lambda`, `clip_epsilon`, …
- `local_feature_dim`, `lstm_hidden_size`, `mlp_hidden_dim`

Promoted numeric baseline: [Fine-Tuning History §8](../engineering/fine_tuning_history.md#8-promoted-baseline-engine-configuration).

Next: [Scalability](scalability.md).
