# Neatness: discover, then stick the clean win

Platforming needs **two objectives**:

1. **Discover** gap commits / rises (needs mild jump cost + entropy + explore).
2. **Prefer clean** finishes (few takeoffs) once a clear exists.

A single static “magic” `jump_reward` tries to do both at once and usually fails one side. Stage B sidesteps that with a **schedule + lock**.

Deep design notes: [Stage B: Jump Cleanliness Polish](../engineering/jump_polish_stage_b.md).

> [!IMPORTANT]
> Hard clears often stay jumpy on first win. Immediate anneal reset on one greedy miss reheats discovery into jump-spam. Hold polish through `polish_fail_grace` misses, keep mirror-only polish augs + mirrored lock clone after clear (jitter/dropout off), and defer lock until after that cycle’s scouts.

## Lever A — Goal Rehearsal Lock

| Knob | Role |
| :--- | :--- |
| `goal_rehearsal_lock` | Master enable |
| `goal_rehearsal_scout_episodes` | Pre-clear stochastic hunters |
| `goal_rehearsal_scout_episodes_polish` | After clear: more scouts (default **10**) |
| `goal_rehearsal_epochs` | BC passes over the locked traj each cycle |
| `goal_rehearsal_mirror_clone` | Also BC a horizontal flip of each lock (default **true**) |

Per cycle: greedy → scouts → **then** lock among that cycle’s victories (fewest takeoffs / confidence tie-break). BC keeps argmax glued to that path (and its mirror) while uncleared collect stays exploratory.

## Lever B — Post-clear jump anneal

| Knob | Role |
| :--- | :--- |
| `jump_reward` | Discovery band (before first clear) |
| `jump_reward_polish` | Harsher target after clear |
| `jump_anneal_cycles` | How fast to reach polish |

After clear, jumpy on-policy wins look worse in return — **without** making first invents impossible.

**Do not anneal `turn_reward`.** Mazes need cheap intentional turns.

## Lever C — Post-clear entropy anneal

| Knob | Role |
| :--- | :--- |
| `entropy_regularization` | Discovery band (escape idle/left spawn collapse) |
| `entropy_regularization_polish` | Lower target after clear (sharper argmax) |
| `entropy_anneal_cycles` | How fast to sharpen (default **6**) |

## Lever D — Post-clear explore anneal (primary neatness speed)

| Knob | Role |
| :--- | :--- |
| `tile_exploration_reward` | Discovery band (beat spawn-idle) |
| `tile_exploration_reward_polish` | Lower after clear (less hop-into-air farming) |
| `explore_anneal_cycles` | How fast to cool explore (default **6**) |

Finish still dwarfs one takeoff; leaving explore at discovery (e.g. `0.075`) after clear keeps PPO sampling jumpy wins. Cooling explore is the main post-clear neatness lever alongside lock coverage.

## Lever E — Fail grace + post-clear mirror-only augs

| Knob | Role |
| :--- | :--- |
| `polish_fail_grace` | Consecutive greedy fails before anneal resets to discovery (default **3**) |
| `mirror_augmentation_prob_polish` | Mirror rate on cleared levels (default **0.5**) |
| `goal_rehearsal_mirror_clone` | Also BC a horizontal flip of each lock (default **true**) |

Misses inside grace: keep polish band + keep Goal Rehearsal Lock; still zero the early-stop victory streak. After grace trips: remove `clear_progress` (discovery again).

Cleared levels keep **mirror** at `mirror_augmentation_prob_polish` but zero spawn/goal jitter and view dropout so collect stays lock-aligned. Showcase/scouts stay unaugmented. Each lock is also rehearsed as a mirrored clone when `goal_rehearsal_mirror_clone` is on (fights rightward prior without requiring mirrored scout wins). Uncleared levels keep full discovery augs.

```mermaid
flowchart TD
  train["Train on level"] --> firstWin["First victorious showcase"]
  firstWin --> annealJ["Anneal jump_reward"]
  firstWin --> annealE["Anneal entropy"]
  firstWin --> annealX["Anneal explore"]
  firstWin --> polishAug["Mirror-only polish augs"]
  firstWin --> scout["More polish scouts"]
  scout --> lock["Lock fewest-takeoff traj"]
  annealJ --> ppo["Collect prefers fewer takeoffs"]
  annealX --> ppo
  polishAug --> ppo
  annealE --> sharp["Policy sharpens"]
  lock --> bc["BC rehearse + mirror clone"]
  ppo --> sticky["Greedy stays neat"]
  sharp --> sticky
  bc --> sticky
  miss["Greedy miss"] --> grace{"fails < polish_fail_grace?"}
  grace -->|yes| sticky
  grace -->|no| invent["Back to discovery band"]
```

## Success check

**Discover under mild J / hot explore / hot entropy, then hold clean greedy play after clear** — survive 1–2 greedy misses without jump-spam reheating; easy flats still neat via lock+explore cool.

`--tune-ej-only` remains a secondary tool. Prefer discovery-safe J + lock/anneal; if you search E/J again, keep a **discovery smoke** on early pits.

## Pattern to reuse later

For any new style failure (wasteful trap triggers, slow puzzles, …):

1. Keep a **discovery-safe** base signal so the skill can be invented.
2. Define **one measurable polish metric** on victorious play.
3. Optionally **scout + lock + rehearse** clean wins.
4. Optionally **anneal** the matching cost (and any discovery bonus that fights polish) only after first success.
5. Do **not** globally tax behaviors future skills will need (cf. turns / mazes).

Next: [Config knobs](config_knobs.md).
