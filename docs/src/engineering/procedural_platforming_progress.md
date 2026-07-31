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
- **CLI Tooling**: `python src/cli/main.py platforming-limits --delta-height N` exposes physics budgets via JSON stdout.

### B. Clearance-Aware Vaulting (`_clearance.py`)
- **Higher Edge Anchoring**: Jump vault ceilings across pits and height shifts are measured relative to $\text{higher\_y} = \min(y_{\text{takeoff}}, y_{\text{landing}})$.
- **Vault Height**: Vault clearance equals at least $(JH + DH)$ tiles above $\text{higher\_y}$, spanning across gap columns and edge overlap bands on both takeoff and landing platforms.
- **Contiguous Drop Clearance**: For drops ($\Delta h < 0$), `paint_span_clearance` extends the upper floor's ceiling across the transition gap, preventing ceiling tiles from blocking the Delver's head as they step off into a fall.

### C. Structure Placement & Enforced Empty Areas (`_structures.py`)
- **Static EEA Enforcement**: `can_place_floor_run` checks that no candidate platform tile overlaps existing `CLEARANCE` (EEA) or `PLATFORM` cells. Overlapping candidates are rejected immediately (structure choice weight drops to 0).
- **Solid Step Face Walls**: In `try_floor_height_shift`, vertical step face walls are painted solid for all rows $y \in [\text{lo\_y}, \text{hi\_y}]$, eliminating hollow notch artifacts (`xx0` edge tips).
- **Configurable Transition Gap Wideness**: Height shifts sample transition gap wideness in range `[min_shift_transition_gap_tiles, max_shift_transition_gap_tiles]`, dynamically providing 1 to 3 tiles of open transition corridor.

### D. Finalization & Actor Anchoring (`_finalize.py`)
- **Solid Perimeter Sealing**: Outer boundary walls seal the entire level grid.
- **Headroom Protection**: `finalize_sketch_dict` reserves `reserve_h = max(delver_h, goal_h, 3)` tiles of standing air above every exposed platform floor before running the interior fill loop.
- **Pit Void Preservation**: Pit gap columns with clearance below floor height propagate open air down to the bottom perimeter wall, preventing the fill algorithm from closing pit chasms.
- **Extremity Anchoring**: Delver (spawn) is placed on the left extremity platform, and Goal is placed on the right extremity platform.

### E. Configuration & Testing
- **Centralized TOML**: Configured via `level/level/procedural_platforming.toml`.
- **Test Suite**: 20 automated unit tests in `level/level/procedural/test_platforming_generator.py` covering delta gap caching, seed reproducibility, solid perimeters, unblocked headroom, and pit void preservation.

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
