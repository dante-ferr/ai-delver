# Engine Protocol (Agentic Fine-Tuning)

Operational ritual for an **orchestrating AI agent** (or developer) improving the **training engine** — HPs, rewards, `intelligence/config.toml`, sim support — measured with eval packs.

**Not** the player coaching loop. Concepts: [Skill Ladder](skill_ladder.md). Level lists: [Eval Packs](eval_packs.md). Map geometry: [Level Authoring](../levels/authoring.md).

Prefer the client CLI over ad-hoc HTTP — [GUI-to-CLI Protocol](../cli/gui_protocol.md).

---

## 0. Roles

| Actor                      | Owns                                                                             |
| -------------------------- | -------------------------------------------------------------------------------- |
| **Player**                 | Coaching _their_ Delver (GUI / `train`)                                          |
| **Agentic AI / developer** | Engine defaults, `tune`, sim coverage, **eval pack requests**, short eval trains |

Eval checkpoints are smoke tests of the engine, not the shipped player Delver (unless a developer explicitly promotes them).

---

## 1. First step after a fine-tune request (mandatory)

As soon as the human asks to fine-tune the engine for a skill family (or “bootstrap platforming”), **before** `tune` / long discussion / inventing maps, the agent must:

1. Propose **S** and **P** ([Eval Packs §1](eval_packs.md#1-inputs)), and explicitly ask the human to confirm or specify them.
2. Confirm (or ask once) whether **S** is already in the **training sim**. If not → stop and plan sim work first ([Skill Ladder](skill_ladder.md)).
3. Run `platforming-limits` when jumps/gaps matter; record rise/gap caps.
4. **Emit the full eval pack request** using the [output template](eval_packs.md#4-output-template-agent--human) — every row filled from the [category + count formula](eval_packs.md).
5. **Wait** for the human to build (or confirm) those levels and reply with final `data/level_saves/` names.
6. Only then proceed to Pass A / B / C and CLI `tune` / eval `train`.

Do **not** invent complex layouts. Do **not** skip the typed level list. The template is the chat-context-free contract.

For platforming bootstrap, the agent may paste the [platforming instance table](eval_packs.md#6-instance-platforming-p--) and still use the full template header (S, P, assumptions, checklist).

---

## 2. Hard rules

1. Orchestrate via client CLI (`poetry run python src/cli/main.py …`).
2. Server up before `train` / `tune` (`make run-ai-dev`, default `localhost:8001`).
3. `--mode static` only.
4. Parse JSON lines (`event` field) on stdout.
5. Prefer `--runs-per-cycle` for smoke trains; `tune` may use `--episodes-per-cycle` (= `env_batch_size`).
6. Success = **sequential mastery** on the curriculum (see §4 `tune`), not a diluted multi-level average.
7. No complex agent-authored layouts; humans build from the emitted list.
8. Extend the CLI rather than one-off HTTP scripts for lifecycle actions.
9. **Pure vision RL**: the Delver must learn from `local_view` (25×25 occupancy, radius 12 → 625 cells) plus `global_state` proprioception / relative goal. No artificial conditional rules or heuristic action overrides. Standing still and backtracking stay unpenalized (elevators, mazes, timing).
10. Fine-tuning runs **once per skill family**; long Optuna budgets are allowed. Search rewards / LR / entropy **first**; enable `--tune-architecture` only as a **second pass** after those stabilize.

---

## 3. Engine surface

| Lever            | Where                                            |
| ---------------- | ------------------------------------------------ |
| LR, entropy, PPO | `intelligence/config.toml` / CLI                 |
| Network sizes    | `config.toml` / CLI (`local_feature_dim`, LSTM, MLP) |
| Rewards          | `config.toml` / CLI                              |
| Collect timing   | `config.toml`                                    |
| Local view       | Fixed radius 12 (25×25) in the intelligence env  |
| HP search        | CLI `tune` (sequential mastery objective)        |
| Sim objects      | `intelligence` + `runtime` / level load          |
| Physics feel     | `delver.toml` / `world.toml` (+ re-check levels) |

Comment non-obvious default changes in `config.toml`.

**Vision note:** binary solid/empty occupancy with radius 12 is sized so 8-tile pits (`platforming-9` / `10`) are visible before the jump, without the full noise of radius 14. Goals are **not** painted into `local_view`; relative goal position lives in `global_state`. A tiny 2D conv over the grid (instead of a dense bag-of-tiles encoder) is a later experiment if geometry learning stalls.

---

## 4. Passes (after levels exist)

Follow [Skill Ladder §3](skill_ladder.md#3-formula-for-each-new-major-skill-s):

| Pass  | Agent / checkpoint                | Levels (from pack) |
| ----- | --------------------------------- | ------------------ |
| **A** | Blank or weak eval agent          | ISO (+ trivial-P)  |
| **B** | Warm-start **P-capable** baseline | ONP + COM          |
| **C** | Same or fresh under new defaults  | RET                |

When P is empty, Pass A on ISO+COM is the whole story; skip Pass B warm-start.

For **platforming bootstrap mastery**, `tune` may also run sequential curriculum on `platforming-1` → `platforming-10` (weight inheritance within each trial) and score **final** argmax clear rates after the full curriculum.

### `tune`

```bash
cd client
poetry run python src/cli/main.py tune \
    --levels "platforming-1,platforming-2,platforming-3,platforming-4,platforming-5,platforming-6,platforming-7,platforming-8,platforming-9,platforming-10" \
    --cycles 15 \
    --episodes-per-cycle 38 \
    --agent engine_eval_agent \
    --trials 10 \
    --eval-runs 15 \
    --tail-k 3 \
    --mastery-threshold 0.8 \
    --server localhost:8001
```

Each trial:

1. Uses a **fresh blank agent** (`{agent}_trial_{n}`) — no cross-trial weight leak.
2. Runs sequential `train` on the level list (Pass-B-style inheritance inside the trial).
3. Runs `--play` mastery eval (`--eval-runs`, default **15** showcases per level for stable WRs).
4. Optuna maximizes the **mean of the `tail_k` lowest per-level win rates** (default `tail_k=3`) so one noisy showcase does not dominate. Always log **min**, **mean**, and the full per-level table.
5. A set is “ideal” / promotable only when **`min` per-level WR ≥ `--mastery-threshold`** (default 0.8). Diluted pack averages (e.g. 9%) are **not** success.

Optuna prunes if `abs(loss) > 20` during train.

**Two-pass search (required practice):**

1. **Pass 1 — rewards / LR / entropy only** (no `--tune-architecture`).
2. **Pass 2 — architecture** (`--tune-architecture`: PPO epochs / minibatch / value coeff and `local_feature_dim` / `lstm_hidden_size` / `mlp_hidden_dim`) once Pass 1 is clearing mid-pack levels.

Apply `best_params` to a longer eval `train`, then promote to `config.toml` with comments when justified.

### Eval `train` (smoke only)

```bash
poetry run python src/cli/main.py train \
    --levels "<eval names>" \
    --cycles 5 \
    --runs-per-cycle 5 \
    --mode static \
    --agent engine_eval_agent \
    --server localhost:8001
```

### Promote when

1. No `error`.
2. Sequential mastery: **`min`** per-level play win rate ≥ 0.8 on the target curriculum (not a diluted pack average). Also inspect mean and the per-level table — do not promote on Optuna’s tail-mean alone if min is below threshold.
3. Pass C retention holds (when P is non-empty).
4. Defaults are commented and reproducible.

---

## 5. New big feature ritual

```text
request → §1 emit eval pack list for S
        → human builds levels
        → land S in training sim (if not done)
        → Pass A → Pass B → Pass C
        → promote defaults
        → players coach
```

| Change                        | Action                                                                     |
| ----------------------------- | -------------------------------------------------------------------------- |
| New platform **layouts** only | No engine ritual; players/`train` on new names                             |
| HP tweak only                 | Short eval / `tune` on **existing** pack; no new list unless coverage gaps |
| Mechanic not in training sim  | Sim first, then §1                                                         |

---

## 6. Sketch import (optional)

If the human used sketches:

```bash
poetry run python src/cli/main.py import-level-sketch \
    --from "data/level_sketches/Some Eval.json" \
    --name "Some Eval"
```

IDs / footprints / borders: [Level Authoring](../levels/authoring.md).

---

## 7. Checklist

```text
[ ] §1: aligned S and P with human, and emitted eval pack table (S, P, every category row)
[ ] Human confirmed level save names
[ ] Sim supports S
[ ] Server up
[ ] Pass A (ISO) — tune / smoke as needed
[ ] Pass B (ONP+COM) if P non-empty — warm-start P-capable baseline
[ ] Pass C (RET)
[ ] Promote config.toml only if justified
[ ] Do not treat eval weights as the player Delver
```
