# Network & PPO

## Actor–critic in one sentence

The network looks at (local view + global state + recurrent memory), outputs **action logits** (policy) and a **value** estimate (how good is this situation), then PPO nudges the policy toward actions that beat the value baseline.

## Architecture (`agent/model.rs`)

```text
local_view (625) ──Linear──► local features
global_state (7) ──LN+Linear──► global features
        └─ concat ─► MLP ─► LSTM ─► shared trunk
                                      ├─ run head (3)
                                      ├─ jump head (2)
                                      └─ value head (1)
```

Widths (`local_feature_dim`, `lstm_hidden_size`, `mlp_hidden_dim`) live in `config.toml` and are Optuna’s **second pass** only (`--tune-architecture`).

The LSTM carries memory across the collect window so “I already jumped” / “I’m mid-gap” can matter without painting history into the grid.

## Train-time action selection

During collect, actions are **sampled** from the categorical distributions (`multinomial`). That is exploration.

Entropy regularization (`entropy_regularization`) pushes distributions toward uniform — more invention, more drift risk for neat argmax play.

## PPO update (`agent/ppo.rs`)

Each cycle builds a `Rollout` tensor buffer (local, global, episode starts, actions, rewards, dones, old log-probs/values), computes **GAE** advantages, then runs clipped policy / value / entropy losses for `ppo_num_epochs`.

Important detail: recurrent sequences restart cleanly when an env episode ends (`episode_starts`).

## Goal Rehearsal = behavioral cloning

`Ppo::rehearse` is **not** another PPO pass on on-policy noise. It clones locked victorious trajectories (observation → recorded actions) for `goal_rehearsal_epochs` so the neat argmax peak is reinforced even when return near-ties jumpy wins.

That is why finish≈1.00 for both neat and jumpy paths can still converge toward the clean one.

Next: [Training cycle](training_cycle.md).
