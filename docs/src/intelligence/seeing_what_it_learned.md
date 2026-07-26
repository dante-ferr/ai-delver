# Seeing what it learned

The same weights behave differently depending on how actions are chosen. Mixing these up is the #1 source of “it was neat, now it’s jumpy” confusion.

## Three run types

| Mode | Action selection | Learns? | Streams trajectory? | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Training collect** | Stochastic sample | Yes (PPO) | No (metrics only) | Invent & improve |
| **Showcase** | Greedy argmax | No (during the pass) | Yes | “What do current weights prefer?” |
| **Play** | Greedy argmax | No | Yes | On-demand mastery eval |

Full matrix and drift diagram: [Run Types](../engineering/run_types.md).

## Showcase is not “best ever”

Each showcase re-runs argmax on **current** weights. It does not freeze the historically best path.

```text
neat Showcase #1  →  more PPO updates  →  jumpy Showcase #2
```

That jumpiness is **weight drift**, not the showcase exploring. Training collect explores; showcase only reads the new decision boundary.

## Why finish reward hides neatness

After `reward_scale()` (dominated by `finished_reward`), neat and jumpy clears both look like ~`1.00` in the UI. Use:

- trajectory field `jump_takeoffs`
- CLI `level_mastery` → `mean_jumps` / `max_jumps`
- pack mean takeoffs when tuning

## Scouts vs showcase

Scouts are stochastic **on purpose** — they hunt cleaner victories for the lock. They are not shown as the main GUI “this is the agent” replay (the greedy showcase is).

## Play eval for mastery

Sequential mastery Optuna / coaching checks use play-mode argmax win rates (`--eval-runs`). Stochastic train WR is a weak proxy for “does the Delver look mastered.”

Next: [Neatness](neatness.md).
