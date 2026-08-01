# Procedural Platforming Generator - Architecture & Implementation Progress

This document tracks the technical implementation, architecture, completed features, and future roadmap for the procedural platforming level generation algorithm in AI-Delver. It is designed to provide full context for engineers and AI agents working on level generation or training curriculum pipelines.

---

## 1. Architecture Overview

The procedural platforming generator produces physics-anchored, clearance-aware platforming levels saved as `LevelSketch` schema instances. The generator builds levels on a growing sparse `SketchGrid`, enforces Enforced Empty Areas (EEA) for locomotion, and finalizes levels by sealing outer perimeter walls and filling uncarved dead space.

```
Physics TOMLs (delver.toml + world.toml)
           │
           ▼
    PlatformingLimits (compute_platforming_limits, max_gap_tiles_for_delta_height)
           │
           ▼
   ProceduralPlatformingGenerator ◄── procedural_platforming.toml / PhaseConstraints
           │
           ├── SketchGrid (PLATFORM, CLEARANCE, EMPTY)
           ├── _clearance.py (paint_span_clearance, paint_floor_clearance)
           ├── _structures.py (try_continue, try_pit, try_floor_height_shift)
           └── _finalize.py (finalize_sketch_dict, actor anchor placement, pit void preservation)
           │
           ▼
     LevelSketch / JSON level saves (ready for GUI preview & Rust physics runtime)
```

---

## 2. What We Have Accomplished

### A. Programmatic Locomotion Envelope (`platforming_limits.py`)
- **Physics Derivation**: Delver Height ($DH$) and Jump Height ($JH$) are dynamically calculated from physics constants (`delver.toml` and `world.toml`).
- **Delta-Height Gap Lookups**: `max_gap_tiles_for_delta_height(delta_h)` simulates semi-implicit Euler coyote jumps for any height delta $\Delta h = y_{\text{landing}} - y_{\text{takeoff}}$ (positive = climb, negative = fall). Out-of-reach climbs return $0$.
- **0.5 Tile Human Safety Margin**: Deducts `0.5` tiles from effective gap reach before flooring (`math.floor((sim_gap_tiles - 0.5) + 1e-6)`), preventing procedural pits from requiring frame-perfect coyote jumps.
- **CLI Tooling**: `python src/cli/main.py platforming-limits --delta-height N` exposes physics budgets via JSON stdout.

### B. Clearance-Aware Vaulting (`_clearance.py`)
- **Higher Edge Anchoring**: Jump vault ceilings across pits and height shifts are measured relative to $\text{higher\_y} = \min(y_{\text{takeoff}}, y_{\text{landing}})$.
- **Vault Height**: Vault clearance equals at least $(JH + DH)$ tiles above $\text{higher\_y}$, spanning across gap columns and edge overlap bands on both takeoff and landing platforms.
- **Drop Chasm Clearance Scoping**: `paint_span_clearance` scopes drop chasm volume to columns past the takeoff edge (`chasm_x0 = takeoff_x1`), preventing solid rock under takeoff platforms from being cleared into empty un-filled rectangles.
- **Chasm Bottom Clamped to Landing Surface**: The chasm volume never clears at or below the landing surface ($y < y_{\text{landing}}$). For climbs the landing slab sits above the takeoff, so clearing down to the takeoff level used to leave hidden air pockets under climb slabs after exterior fill.

### C. Structure Placement & Enforced Empty Areas (`_structures.py`)
- **Static EEA Enforcement**: `can_place_floor_run` checks that no candidate platform tile overlaps existing `CLEARANCE` (EEA) or `PLATFORM` cells. Overlapping candidates are rejected immediately (structure choice weight drops to 0).
- **Solid Step Face Walls**: In `try_floor_height_shift`, vertical step face walls are painted solid for all rows $y \in [\text{lo\_y}, \text{hi\_y}]$, eliminating hollow notch artifacts (`xx0` edge tips).
- **Climb Shift Clearance Simplification**: In `try_floor_height_shift`, contiguous climbs ($\Delta h > 0$) set `requires_jump = False` and use ambient `clearance_h`, removing unneeded $JH + DH$ vault ceilings above upper landing edges while maintaining the transition gap required for reaching the upper floor.
- **Drop Landing Runway Guarantee**: `try_floor_height_shift` enforces `length = max(length, drop_depth + 1)` for drops, ensuring the landing platform provides enough horizontal runway before subsequent structures can generate.
- **Configurable Transition Gap Wideness**: Height shifts sample transition gap wideness in range `[min_shift_transition_gap_tiles, max_shift_transition_gap_tiles]`, dynamically providing 1 to 3 tiles of open transition corridor.
- **Bidirectional Travel**: All structures (`try_continue`, `try_pit`, `try_floor_height_shift`, `try_switchback`) are direction-agnostic and grow the path along `PathHead.direction` ($+1$ right, $-1$ left). The generator samples the initial travel direction per level and mirrors the spawn platform, so levels can run left-to-right or right-to-left.

### D. Finalization & Actor Anchoring (`_finalize.py`)
- **Solid Perimeter Sealing**: Outer boundary walls seal the entire level grid.
- **Un-escapable Pit Depth Enforcement**: In `finalize_sketch_dict`, pit gap columns propagate open air for at least `min_pit_depth = math.ceil(JH) + 1` (5 tiles) below the floor edge, preventing the Delver from jumping out of pit voids.
- **Pit Span Translation Alignment**: Registered pit columns are translated with the same `+1` wall offset as `to_local`. The previous off-by-one shifted every pit span one column left, carving open air under the takeoff lip (1-tile cut keeping the upper floor tile) and leaving the last gap column plugged at the pit's right edge.
- **Bottom Margin Protection**: `finalize_sketch_dict` reserves `bottom_margin_tiles = min_pit_depth` below the lowest platform, ensuring pits near the bottom of the sketch maintain full 5-tile depth above the bottom boundary wall.
- **Headroom Protection**: `finalize_sketch_dict` reserves `reserve_h = max(delver_h, goal_h, 3)` tiles of standing air above every exposed platform floor before running the interior fill loop.
- **Extremity Anchoring**: Delver (spawn) and Goal are anchored at the trailing edges of travel on the start / goal segments — left/right extremities for left-to-right levels, flipped for right-to-left levels (`travel_direction` selects the anchor polarity).

### E. Configuration & Testing
- **Centralized TOML**: Configured via `level/level/procedural_platforming.toml`.
- **Travel Direction Bias**: `ltr_direction_bias` in $[-1, 1]$ controls level orientation: $+1$ always left-to-right, $-1$ always right-to-left, $0$ equal odds ($P(\text{LTR}) = (1 + \text{bias}) / 2$). Extremes short-circuit without drawing RNG, so $\text{bias} = \pm 1$ keeps seeds exactly mirrored between orientations.
- **Test Suite**: 27 automated unit tests in `level/level/procedural/test_platforming_generator.py` covering delta gap caching, seed reproducibility, solid perimeters, unblocked headroom, pit void preservation, pit span alignment, solid fill under climb landings, floating platform tile detection, and travel direction bias orientation/invariants.

---

## 3. What Remains To Be Implemented (Future Roadmap)

1. **Multi-Path Branching (Forks & Merges)**:
   - Allow single paths to fork into alternative routes at lower/higher difficulty levels (constrained to max 1 or 2 active forks).
   - Implement path merging logic (joining a sub-path back into its parent corridor).

2. **Pattern Overlays**:
   - Re-enable and fine-tune optional structures: neighbor pits with short platform bridges (`neighbor_pit_bridge_odds`), and delay ledges at $\frac{3}{4} JH$ (`delay_ledge_odds`).

3. **Curriculum Training Integration**:
   - Integrate `curriculum.py` phases into the RL training server so Delvers train progressively across obstacle-specific phases (`flat_run` $\rightarrow$ `same_height_pits` $\rightarrow$ `rises` $\rightarrow$ `falls` $\rightarrow$ `mixed`).

4. **Directional Turn Re-enabling**:
   - Turn-arounds (`turn_weight` and `switchback_weight`) are currently disabled ($0.0$) in `procedural_platforming.toml` for single-path linearity validation. Re-enable them when curriculum phases require vertical switchbacks.

---

## 4. Key Module Sitemap

| File Path | Description |
| :--- | :--- |
| [`level/level/procedural_platforming.toml`](file:///home/dante/Code/projects/ai-delver/level/level/procedural_platforming.toml) | Centralized TOML configuration file for generation parameters. |
| [`level/level/sketch/platforming_limits.py`](file:///home/dante/Code/projects/ai-delver/level/level/sketch/platforming_limits.py) | Physics envelope & delta-height max gap computation module. |
| [`level/level/procedural/platforming_generator.py`](file:///home/dante/Code/projects/ai-delver/level/level/procedural/platforming_generator.py) | Main generator class (`ProceduralPlatformingGenerator`) and step loop. |
| [`level/level/procedural/_clearance.py`](file:///home/dante/Code/projects/ai-delver/level/level/procedural/_clearance.py) | Vault and corridor clearance painting (`paint_span_clearance`, `paint_floor_clearance`). |
| [`level/level/procedural/_structures.py`](file:///home/dante/Code/projects/ai-delver/level/level/procedural/_structures.py) | Structure trial functions (`try_continue`, `try_pit`, `try_floor_height_shift`). |
| [`level/level/procedural/_finalize.py`](file:///home/dante/Code/projects/ai-delver/level/level/procedural/_finalize.py) | Grid crop, perimeter wall sealing, interior fill, and actor anchoring. |
| [`level/level/procedural/test_platforming_generator.py`](file:///home/dante/Code/projects/ai-delver/level/level/procedural/test_platforming_generator.py) | Unit test suite. |
