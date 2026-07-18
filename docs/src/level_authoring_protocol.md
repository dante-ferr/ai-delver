# Level Authoring Protocol (Sketches)

Rules for levels that feed the **training-engine fine-tuning** stage: a human-authored eval / curriculum pack the developer or agentic AI runs through `tune` and short smoke `train`s to judge whether HPs, rewards, and the sim actually learn. See [Agentic Fine-Tuning Protocol](agentic_fine_tuning_protocol.md).

Sketches are dense grids of gameplay IDs; `import-level-sketch` expands them into full editor saves. You may also author full levels in the editor — the spacing rules still apply.

This protocol is **not** the player coaching guide. The same maps may later be reused when players train Delvers, but the authoring checklist here exists so the engine fine-tune stage has a clear, skill-covered eval set.

---

## 0. Who authors levels (current policy)

**Humans design the fine-tuning eval pack. Orchestrating agents do not invent layouts for now.**

Today’s models are unreliable at spatial level design: they can satisfy jump/gap math and still produce unreadable routes, decorative dead-end ledges, and cheese paths. Until that changes, the engine-tuning agent must:

1. **Ask the human** for the eval / curriculum levels (editor saves under `client/data/level_saves/`, and/or sketches under `client/data/level_sketches/`).
2. **Not** generate complex multi-segment gauntlets or “clever” zigzag maps on its own.
3. Run `platforming-limits`, validate that human levels respect the budgets below, import sketches if needed, then use the pack with `tune` / short eval `train` per the fine-tuning protocol.
4. Only author **trivial** textbook sketches if the human explicitly asks (e.g. a single gap or single rise) — and prefer human review before using them in fine-tune eval.

Revisit this section when stronger models make agentic layout authoring trustworthy again.

---

## 1. Always refresh physics limits before authoring

Physics tunables live in:

- [`runtime/src/world_objects/delver/delver.toml`](../../runtime/src/world_objects/delver/delver.toml)
- [`runtime/src/engine/world.toml`](../../runtime/src/engine/world.toml)

Those values change over time. **Do not hard-code jump heights or gap sizes in prompts or memory.** Before writing or reviewing a level for the fine-tune pack, run:

```bash
cd client
poetry run python src/cli/main.py platforming-limits
```

Parse the JSON line with `"event": "platforming_limits"`. Use the `recommended_*_tiles` fields when placing platforms.

Optional overrides:

```bash
poetry run python src/cli/main.py platforming-limits \
    --delver-toml ../runtime/src/world_objects/delver/delver.toml \
    --world-toml ../runtime/src/engine/world.toml
```

---

## 2. How limits are derived

The CLI mirrors the locomotion model used in training (`LocomotionMotor` + Rapier ticks at `physics_fps`):

| Quantity | How it is computed |
| :--- | :--- |
| Steady run speed | `vx_ss = min(move_force / linear_damping, max_vx)` (motor sets `vx` each tick) |
| Jump height | `h = jump_impulse² / (2 · \|gravity\|)` — matches Rapier apex within ~1px |
| Max gap | **Coyote edge jump**: run off a ledge for up to `jump_tolerance_max`, then jump, hold run, land at takeoff height; add `player_width` for toe overhang on both ledges |
| Tile conversion | divide by `tile_width` / `tile_height` (16px) |

**Authoring budgets** (`recommended_*_tiles`):

- `recommended_max_rise_tiles` ← `floor` of apex height as **surface-to-surface** row delta (~4 with current tunables; apex is tuned a few px above that so wall-kiss landings stay reliable)
- `recommended_max_stack_tiles_including_floor` ← rise + 1 (secondary; only if you count the floor cell in a column)
- `recommended_max_gap_tiles` ← `round` of coyote + toe-overhang reach
- `recommended_min_ceiling_clearance_tiles` ← standing height + mid-jump clearance

### How to count tiles in a sketch

**Rise** is the authoring budget: landing surface minus standing surface, in whole tiles (16px). Do **not** include the floor tile you stand on.

```text
  y (px)     grid (from floor top)
  ------     ---------------------
   80  ----  +5  (unreachable at current tunables)
   64  ====  +4  landing surface  ← recommended max rise
   48  ----  +3
   32  ----  +2
   16  ====  +0  floor top (standing surface)
    0  ....  floor tile body
```

Example: stand on row `11`, land on row `7` → rise `4` (64px). That matches a pillar of **four** solid cells stacked **above** the floor top in an adjacent column.

**Gap**: number of **empty** cells between two same-height floor platforms. Platforms at columns `2` and `11` with empties `3..10` → gap `8`.

Apex is intentionally above `recommended_max_rise_tiles` (e.g. ~70px for a 64px / +4 max) so kissing a pillar wall on the way up still clears the lip. Always re-run the CLI after physics changes.

---

## 3. Surrounding walls (enforced)

Every sketch **must** form a closed playable box: the entire perimeter of the grid is solid `platform`.

`import-level-sketch` **programmatically adds** `platform` to any missing perimeter cell. Prefer drawing the border explicitly so the sketch matches what you intend to see.

Rules of thumb:

- Put floor / walkable surfaces on the **bottom** row (and interior platforms).
- Place `delver` and `goal` in **empty interior cells** (usually one tile above a floor platform). They cannot share a cell with `platform` — `platforms` and `essentials` are concurrent layers, so one removes the other.
- **`delver` / `goal` cells are bottom-left anchors.** Delver is currently **1×3** (`ceil(player_height / tile_height)`); Goal is **2×2**. The ID marks the standing (bottom-left) cell; the body occupies cells above and to the right. Keep the whole footprint interior and free of platforms.
- Do not place `delver`/`goal` (or any cell of their footprint) on the perimeter; surrounding walls must stay solid.
- Do not rely on open map edges; falling below the world still kills the Delver.

---

## 4. Spacing guidelines

When placing platforms relative to each other:

1. Run `platforming-limits` and read `recommended_max_gap_tiles` / `recommended_max_rise_tiles`.
2. **Horizontal gaps** between same-height ledges must be ≤ `recommended_max_gap_tiles` empty cells.
3. **Vertical rises** (floor-top to landing-top, in tiles) must be ≤ `recommended_max_rise_tiles`.
4. Under ceilings / tunnels, leave at least `recommended_min_ceiling_clearance_tiles` of free cells above the standing surface when a jump is required.
5. Thin pillars with a max-length gap are harder than the estimate (need full run-up to reach `vx_ss` before the edge).

For the fine-tune eval pack, staying **1 tile under** the recommended maxima on most maps is still a good idea; reserve true maxima for one exam map. The CLI reports the physical ceiling, not the easiest teaching gap.

**Route readability (platform-only):** every ledge should sit on an obvious path from spawn to goal. Avoid shallow “pits” that are really walkways under a gap (without spike traps, those are free shortcuts). Prefer floating platforms over deep air so missing a jump costs time, not an accidental alternate route to the goal. Ambiguous routes make `tune` / smoke-train win rates hard to interpret.

---

## 5. Fine-tuning eval pack (platforming)

Use this checklist when **you** (the human) build the levels the engine fine-tune stage will run. The training sim is **platform + delver + goal only** — no traps/enemies yet.

Goal of the pack: give `tune` and short eval `train`s a **representative skill coverage** so promoted defaults actually learn platforming — not a random handful of maps.

### How many levels

| Tier | Count | Purpose |
| :--- | ---: | :--- |
| Core skills | **6–8** | One clear mechanic each (below) |
| Combo / exam | **2–3** | Mix several skills on one readable route |
| **Total** | **~8–11** | Enough diversity for mixed `--levels` in `tune` / eval without a huge catalog |

Fewer than ~6 and the fine-tune signal under-sees layout variety; more than ~12 rarely helps until new mechanics exist in the sim.

### What each core level should teach

Build separate short levels (easy to medium). Stay ≤ `recommended_*` from `platforming-limits`; prefer **max − 1** on most eval maps, and reserve true maxima for one exam map.

| # | Skill to implement | Design notes |
| ---: | :--- | :--- |
| 1 | Walk to goal | Flat or trivial floor; proves spawn/goal and basic run |
| 2 | Short gap | Same-height gap ~3–4 empty tiles; comfortable run-up |
| 3 | Medium gap | ~5–6; still under the CLI max |
| 4 | Long / coyote gap | ~max − 1 (or max on an exam); needs edge timing / coyote |
| 5 | Short rise | Surface rise +1 or +2 |
| 6 | Medium rise | +3 |
| 7 | Max rise | +`recommended_max_rise_tiles` with a clear wall-kiss or run-up onto a wide ledge |
| 8 | Descent / drop | Downward path or drop onto a lower platform, then to goal (not only climbing) |

Optional extras if you want more coverage: **stair-step ascent** (several +1/+2 in a row), **leftward jump** after a rightward approach, **narrow landing** (2–3 tile ledge).

### Combo / exam levels (2–3 maps)

Each should chain **at least three** skills from the table on one intentional route (e.g. gap → rise → gap → goal). Requirements:

- A human can see the intended path in a few seconds.
- No decorative wall stubs that look like path but aren’t.
- No under-gap floor that skips the challenge.
- Still fully clearable within physics limits (playtest once yourself).

### How the pack is used in fine-tuning

1. Hand the named level saves to the engine orchestrator (or leave them under `data/level_saves/`).
2. Orchestrator runs `tune` and/or short eval `train` on a representative subset (or the full pack) — [Agentic Fine-Tuning Protocol](agentic_fine_tuning_protocol.md).
3. Promote HPs / rewards to `config.toml` only when win rate / learning curve on this pack improves.
4. Do **not** treat eval checkpoints as the product Delver; player coaching is a separate loop.
5. After traps/enemies exist in the **training sim**, extend this pack with mechanic-specific and **combo** eval maps, then retune the engine again.

---

## 6. Sketch → fine-tune workflow

```text
human: design eval pack (editor and/or sketches), playtest
        → platforming-limits (sanity-check spacing)
        → import-level-sketch [--force]   # if using sketches
        → engine agent: tune / short eval train on those levels
        → promote defaults if justified
```

Element ID rules: [Agentic Fine-Tuning Protocol §6](agentic_fine_tuning_protocol.md#6-levels-for-engine-work).
