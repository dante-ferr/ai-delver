# Eval Packs (Level List Formula)

Chat-context-free rules for **what levels** the engine fine-tune needs. The orchestrating agent must **emit this list to the human** before asking them to build maps (see [Engine Protocol](engine_protocol.md) §1).

Humans draw the maps. Agents do not invent complex layouts. Geometry / jump spacing: [Level Authoring](../levels/authoring.md). Staging Pass A/B/C: [Skill Ladder](skill_ladder.md).

---

## 1. Inputs

When starting (or expanding) an engine fine-tune, fix:

| Symbol | Meaning |
| :--- | :--- |
| **S** | New major skill family being fine-tuned (e.g. `platforming`, `traps`, `puzzles`, `physics_handling`) |
| **P** | Prior families already in the training sim and previously fine-tuned (ordered list; empty if S is the first) |

Also run `platforming-limits` if maps involve jumps/gaps, and note `recommended_max_*` for design notes in the list.

---

## 2. Level categories (always these four)

For every S, the agent’s list must cover:

| Code | Name | Intent | Pass |
| :--- | :--- | :--- | :--- |
| **ISO** | `S_isolated` | Teach/measure **S** with **trivial or minimal** dependence on P (blank-agent signal) | A |
| **ONP** | `S_on_P` | Simple **S** that still needs **competent P** (e.g. trap after a real jump) | B |
| **COM** | `S_combo` | **S + prior skills** on one readable route | B |
| **RET** | `P_retention` | **Prior-only** maps (no new S requirement) so Pass C can detect regressions | C |

If **P** is empty: omit ONP/RET that reference P; ISO + COM within S (skill composition inside platforming) is enough. That is the platforming instance below.

---

## 3. Counts (strict ranges)

| Tier | Count | Category codes |
| :--- | ---: | :--- |
| ISO core | **4–8** | One clear sub-skill of S each |
| ONP | **2–4** | S with non-trivial P |
| COM | **2–4** | Mix S with P (pairwise first; one fuller mix if \|P\| ≥ 2) |
| RET | **2–4** | Reuse named levels from the previous pack(s) for P; do not redesign unless missing |
| **Total new maps to build** | **~8–14** | Exclude RET if those files already exist |

Fewer than ~6 new maps under-sees S; more than ~14 rarely helps one fine-tune stage.

---

## 4. Output template (agent → human)

The agent must print **exactly** this structure (fill every row; use `n/a` only if P is empty and the category does not apply):

```markdown
## Eval pack request: S=<skill> | P=[<prior>, ...]

### Assumptions
- Training sim supports: <list>
- platforming-limits (if needed): rise≤N gap≤M
- Baseline checkpoint for Pass B: <name or "none — P empty">

### Level list

| ID | Category | Suggested name | Skill to implement | Design notes | Pass |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | ISO | Eval <S> … | … | … | A |
| … | … | … | … | … | … |

### Human checklist
- [ ] Build each non-RET row (editor or sketch); playtest clearable
- [ ] Confirm RET rows already exist as named saves (or build if missing)
- [ ] Reply with final level names under data/level_saves/
```

**Suggested name** pattern: `Eval <S> <short>` (e.g. `Eval Traps Spike Flat`, `Eval Platform Gap Med`).

**Skill to implement** = one line, like the platforming table (walk, short gap, … / avoid spike, timed hazard, …).

**Design notes** = concrete constraints (tile counts, “trivial floor”, “needs +2 rise then spike”, “combo: gap + lever”). Stay ≤ physics limits; prefer max−1 except one exam row.

---

## 5. Category rules by dependence

### ISO (`S_isolated`)

- Maximize signal for **S**.
- Keep P demand **minimal**: flat floors, no max gaps/rises, no stacked prior mechanics.
- Example traps: walk into visible spike corridor on flat ground to goal.
- Example puzzles: box on same flat screen as plate; no jumps required.

### ONP (`S_on_P`)

- Must be **impossible or pointless** without competent P.
- Example traps: spike pit beyond a medium gap; crumbling floor after a +3 rise.
- Still “simple” S — one trap idea, not a gauntlet.

### COM (`S_combo`)

- Chain **≥2** of: sub-skills of S, and/or skills from P.
- Readable path in a few seconds; no decorative stubs; no under-gap cheese.
- If \|P\| ≥ 2, include at least one map that mixes **S + two priors** when the sim supports both.

### RET (`P_retention`)

- Prefer **existing** eval names from the prior pack (e.g. platforming `Eval Walk`, `Eval Gap Med`).
- Agent lists them by **exact save name**; human only builds if missing.

---

## 6. Instance: platforming (P = ∅)

Current first-family pack. Agent should emit this list when fine-tuning platforming (or when bootstrapping the engine).

| ID | Category | Suggested name | Skill to implement | Design notes | Pass |
| ---: | :--- | :--- | :--- | :--- | :--- |
| 1 | ISO | Eval Platform Walk | Walk to goal | Flat / trivial floor | A |
| 2 | ISO | Eval Platform Gap Short | Short gap | Same-height gap ~3–4; run-up | A |
| 3 | ISO | Eval Platform Gap Med | Medium gap | ~5–6; under CLI max | A |
| 4 | ISO | Eval Platform Gap Long | Long / coyote gap | ~max−1 (or max on exam) | A |
| 5 | ISO | Eval Platform Rise Short | Short rise | +1 or +2 | A |
| 6 | ISO | Eval Platform Rise Med | Medium rise | +3 | A |
| 7 | ISO | Eval Platform Rise Max | Max rise | +`recommended_max_rise_tiles`; wide ledge | A |
| 8 | ISO | Eval Platform Descent | Descent / drop | Drop to lower platform then goal | A |
| 9 | COM | Eval Platform Combo A | Gap + rise + goal | ≥3 skills; readable route | A |
| 10 | COM | Eval Platform Combo B | Alternate mix | e.g. descent + gap + rise | A |

ONP / RET: `n/a` (P empty). Optional extras: stair-step ascent, leftward jump, narrow landing — add as ISO only if the core 8 are done.

---

## 7. Instance sketch: traps (P = [platforming])

Illustrative — agent fills a full table when traps exist in the sim:

| Category | Examples of “skill to implement” |
| :--- | :--- |
| ISO | Visible floor spikes on flat; slow hazard on flat path to goal |
| ONP | Spike beyond medium gap; hazard after short rise |
| COM | Gap → rise → spike → goal; platform combo + one trap |
| RET | `Eval Platform Walk`, `Eval Platform Gap Med`, `Eval Platform Rise Med`, `Eval Platform Combo A` |

Same pattern for puzzles / physics_handling with S-specific ISO rows and RET pointing at the latest prior pack names.
