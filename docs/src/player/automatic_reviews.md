# Automatic Reviews

How AI Delver’s automatic review passes work: when they arm, what happens during a pass, and how that differs from what you see in the GUI (showcases vs real training).

This is a **player-coaching** feature (client curriculum). It is not the same as engine Pass C / RET eval packs in [Agentic Fine-Tuning](../agentic_fine_tuning/eval_packs.md).

For the broader forgetting-prevention story (combo levels, LR scaling, checkpoints), see [Player Curriculum](curriculum.md).

---

## 1. Why reviews exist

Sequential coaching (train level A, then B, then C) tends to **overwrite** older skills. Automatic reviews keep previously trained levels in the PPO mix every so often so the Delver does not forget hard-won behavior.

**Industry note:** rehearsing old tasks in the mix (experience replay / multi-task rehearsal) is a standard continual-learning tool. What does *not* scale is draining **all** prior levels after every short focus block. Delver therefore uses a **bounded** dose: fixed episodes per reviewed level (`R`), at most `K` levels per arm, after `E` focus episodes.

Reviews are a third shield alongside:

* Coach-built **combo levels**
* **Lower learning rate** when warm-starting a brand-new level

Longer-term, parameter protection (e.g. EWC) is tracked on the [engineering roadmap](../engineering/roadmap.md#3-weight-protection-as-an-alternative-or-complement-to-level-rehearsal) as a possible complement.

---

## 2. Knobs (defaults)

| Knob | Default | Meaning |
| --- | --- | --- |
| `E` | **8000** | Focus episodes between review arms (`focus_episodes_between_passes`) |
| `R` | **100** | Target episode slots **per level** in a review chunk (`review_episodes_per_level`) |
| `K` | **5** | Max prior levels scheduled when arming (`review_levels_per_arm`) |

Per arm, review cost is about `R × K` = **500** episode slots vs **8000** focus (~6% overhead), whether the career has 10 or 50 maps. Full history is covered across many arms via a round-robin cursor (`review_arm_cursor`), not in one giant sweep.

---

## 3. Two kinds of phase

| Kind | When | Level mix sent to `/train` | Session budget |
| --- | --- | --- | --- |
| **Focus** | `review_pass_queue` is empty | Coach-selected levels only | Coach cycles / runs |
| **Review** | `review_pass_queue` is non-empty | **Review-only** priors from the queue (up to `min(K, max_training_levels, queue)`) | Overridden: `ceil(R × L / episodes_per_cycle)` cycles |

The server does not know “focus” vs “review.” It only static-mixes whatever level list the CLI sends. Planning and bookkeeping live in the client (`review_planner` + `metadata.json`).

`--play` never arms or advances review state.

---

## 4. When a review batch is armed

Weight drift scales with **how much new experience** was collected, not how many times you clicked Train.

1. During a **focus** phase, the CLI counts episodes (from WebSocket `metrics`, with a cycles × episodes fallback).
2. On a successful **`model_weights`** write, those episodes are added to `focus_episodes_since_pass`.
3. When that counter reaches **`E`**, the client resets the counter and **arms up to `K` priors** into `review_pass_queue` (round-robin over `trained_levels` from `review_arm_cursor`).
4. Review then runs as a **separate** `/train` in the same Train action when possible (see mid-session chaining), or on the next Train if the click ended earlier.

Review-phase episodes **do not** increase `focus_episodes_since_pass`.

Curriculum fields change **only** after model weights are saved — not on interval checkpoints, and not if the stream dies without weights.

---

## 5. Mid-session chaining

One GUI/CLI Train click can auto-chain multiple server sessions:

1. If a review queue is already pending → drain one review batch first.
2. Run focus (optionally **split** if the requested session alone would cross `E`: focus until the threshold, then review, then leftover focus).
3. If focus armed a queue → immediately run a budgeted review phase (no second button press).
4. Emit `training_phase` = `focus` | `review` so the GUI can drive two progress bars.

True mid-cycle mix swaps are not supported (the server fixes the level list for one `/train`). Chaining separate sessions is the client workaround.

---

## 6. What happens inside a review phase

### Training collect (what actually updates weights)

The intelligence server assigns parallel envs round-robin across the level list:

```text
env_i → levels[i % len(levels)]
```

With `L` levels in a **review-only** mix, each level gets about `1/L` of collect for the whole review budget. The CLI sizes cycles so total episode slots ≈ `R × L`.

### Chunking

`max_training_levels` (from `/init`) caps **one session’s** mix only. Lifetime `trained_levels` is unbounded. Each arm schedules at most `K` levels; further history waits for later arms.

### Commit after weights

On `model_weights`:

* Levels in this phase’s review chunk are removed from `review_pass_queue`
* Coach levels still join `trained_levels` when focus commits (not during a pure review phase)
* Focus counter stays unchanged during review

---

## 7. Showcases vs training (common confusion)

See also [Run Types](../engineering/run_types.md).

| | Training collect | Showcase |
| --- | --- | --- |
| When | Continuously each cycle | Once per level in the mix, **after** each cycle |
| Learning | Yes (PPO) | No (greedy eval) |
| Streamed to client as replay | No | Yes (unless filtered) |

**Client persistence:** review-level showcases are not saved under the agent's trajectories folder (`progress` events carry `is_review: true`, `persisted: false`). Coach/focus showcases still save as usual. Training collect for review levels is unchanged (already server-only).

**GUI:** the train panel shows a focus progress bar and, when a review phase runs in the same Train, a second **Reviewing levels** bar sized to expected review showcases (`cycles × L`).

Across sessions, reviews remain a minority of experience: they only arm after ~`E` focus episodes, and each arm costs about `R × K` slots.

```text
Focus (coach) … until focus_episodes ≥ E
        → Review (up to K priors, ~R episodes each, review-only mix)
        → Focus again …
```

---

## 8. Metadata and events

`data/agents/<agent>/trajectories/metadata.json` (curriculum fields):

```json
{
  "trained_levels": ["L1", "L2", "L3"],
  "level_hashes": { "L1": "<hash>" },
  "review_state": {
    "focus_episodes_between_passes": 8000,
    "focus_episodes_since_pass": 1200,
    "review_episodes_per_level": 100,
    "review_levels_per_arm": 5,
    "review_pass_queue": [],
    "review_arm_cursor": 0
  }
}
```

CLI events:

* `review_plan` — levels, queue remaining, `E`/`R`/`K`, target episodes
* `training_phase` — `focus` | `review`, `expected_progress_steps`
* `progress` — includes `training_phase`, `is_review`, `persisted`

See [Commands Reference](../cli/commands.md#output-and-event-formats).

Checkpoint bundles store the same curriculum snapshot beside weights so restores stay aligned — [Curriculum §6](curriculum.md#6-checkpoint-bundles-weights--curriculum).

---

## 9. Implementation pointers

| Piece | Path |
| --- | --- |
| Planner / commit | `client/src/cli/commands/review_planner.py` |
| Train wiring / phase chain | `client/src/cli/commands/train.py` |
| Static env mix | `intelligence/src/trainer/loop.rs` |
| Defaults | `E=8000`, `R=100`, `K=5` |
