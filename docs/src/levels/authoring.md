# Level Authoring Protocol (Geometry & Sketches)

How to draw **legal, readable** levels (editor or sketches): physics spacing, borders, footprints, sketch schema.

**What levels to build for engine fine-tuning** (the skill list / eval pack formula the agent must send you): [Eval Packs](../agentic_fine_tuning/eval_packs.md).  
**Fine-tune ritual:** [Agentic Fine-Tuning](../agentic_fine_tuning/index.md).

---

## 0. Who draws the maps

**Humans** author layouts. Orchestrating agents **list** required eval levels via the Eval Packs template, then wait — they do not invent complex gauntlets.

Agents may: run `platforming-limits`, validate spacing, import human sketches, run `tune` / eval `train` on named saves.

---

## 1. Always refresh physics limits

```bash
cd client
poetry run python src/cli/main.py platforming-limits
```

Configs: [`delver.toml`](../../../runtime/src/world_objects/delver/delver.toml), [`world.toml`](../../../runtime/src/engine/world.toml).

Use `recommended_max_rise_tiles`, `recommended_max_gap_tiles`, `recommended_min_ceiling_clearance_tiles`. Prefer **max − 1** on most eval maps; one exam map may use the true max.

---

## 2. How limits are derived

| Quantity | How it is computed |
| :--- | :--- |
| Steady run speed | `vx_ss = min(move_force / linear_damping, max_vx)` |
| Jump height | `h = jump_impulse² / (2 · \|gravity\|)` |
| Max gap | Coyote edge jump + `player_width` toe overhang |
| Tiles | divide by 16px |

### Counting rise / gap

**Rise** = landing surface − standing surface in tiles (do not count the floor tile you stand on).

```text
  y (px)     from floor top
   64  ====  +4  max reliable rise (current tunables)
   48  ----  +3
   32  ----  +2
   16  ====  +0  floor top
```

**Gap** = empty cells between two same-height floor platforms.

---

## 3. Surrounding walls

Perimeter must be `platform` (`import-level-sketch` seals missing border cells).

- `delver` / `goal` in empty **interior** cells (usually above a floor). Never share a cell with `platform`.
- Anchors are **bottom-left**. Delver **1×3**, Goal **2×2** — whole footprint interior and clear of platforms.
- No open map edges as a design crutch; falling below the world kills.

---

## 4. Spacing & readability

1. Gaps ≤ `recommended_max_gap_tiles`.
2. Rises ≤ `recommended_max_rise_tiles`.
3. Jump ceilings ≥ `recommended_min_ceiling_clearance_tiles`.
4. Thin pillars + max gaps need full run-up.
5. Obvious path spawn → goal; no decorative stubs; no shallow under-gap walkways that cheese the challenge (ambiguous routes poison eval win rates).

---

## 5. Sketch schema

```json
{
  "name": "Eval Platform Gap Med",
  "grid_size": [20, 12],
  "cells": [
    [null, null, "platform"],
    ["delver", null, "goal"]
  ]
}
```

| Rule | Detail |
| :--- | :--- |
| IDs | `platform`, `delver`, `goal` only (MVP) until sim grows |
| Grid | `cells[y][x]`; row 0 = top |
| Uniques | One delver + one goal anchor, both interior |

```bash
poetry run python src/cli/main.py import-level-sketch \
    --from "data/level_sketches/….json" \
    --name "Eval …"
```

---

## 6. Workflow with fine-tuning

```text
agent: emit eval pack table (Eval Packs formula)
human: build maps per table + this geometry protocol
        → import-level-sketch if needed
        → agent: Pass A/B/C (Engine Protocol)
```
