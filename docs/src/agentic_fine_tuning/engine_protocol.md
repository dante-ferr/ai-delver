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

1. Set **S** and **P** ([Eval Packs §1](eval_packs.md#1-inputs)).
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
6. Success = better defaults / learnability on the eval pack — not “ship a master Delver.”
7. No complex agent-authored layouts; humans build from the emitted list.
8. Extend the CLI rather than one-off HTTP scripts for lifecycle actions.

---

## 3. Engine surface

| Lever            | Where                                            |
| ---------------- | ------------------------------------------------ |
| LR, entropy, PPO | `intelligence/config.toml` / CLI                 |
| Rewards          | `config.toml` / CLI                              |
| Collect timing   | `config.toml`                                    |
| HP search        | CLI `tune`                                       |
| Sim objects      | `intelligence` + `runtime` / level load          |
| Physics feel     | `delver.toml` / `world.toml` (+ re-check levels) |

Comment non-obvious default changes in `config.toml`.

---

## 4. Passes (after levels exist)

Follow [Skill Ladder §3](skill_ladder.md#3-formula-for-each-new-major-skill-s):

| Pass  | Agent / checkpoint                | Levels (from pack) |
| ----- | --------------------------------- | ------------------ |
| **A** | Blank or weak eval agent          | ISO (+ trivial-P)  |
| **B** | Warm-start **P-capable** baseline | ONP + COM          |
| **C** | Same or fresh under new defaults  | RET                |

When P is empty, Pass A on ISO+COM is the whole story; skip Pass B warm-start.

### `tune`

```bash
cd client
poetry run python src/cli/main.py tune \
    --levels "<comma-separated eval names for this pass>" \
    --cycles 5 \
    --episodes-per-cycle 38 \
    --agent engine_eval_agent \
    --trials 10 \
    --server localhost:8001
```

Optuna maximizes win rate; prunes if `abs(loss) > 20`. Apply `best_params` to a longer eval `train`, then promote to `config.toml` with comments when justified.

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
2. Clear rise in victories / return on the target pass levels.
3. Pass C retention holds.
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
[ ] §1: emitted eval pack table (S, P, every category row)
[ ] Human confirmed level save names
[ ] Sim supports S
[ ] Server up
[ ] Pass A (ISO) — tune / smoke as needed
[ ] Pass B (ONP+COM) if P non-empty — warm-start P-capable baseline
[ ] Pass C (RET)
[ ] Promote config.toml only if justified
[ ] Do not treat eval weights as the player Delver
```
