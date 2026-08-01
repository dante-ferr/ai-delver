"""Tests for clearance-aware procedural platforming generation."""

from __future__ import annotations

import unittest

from level.config import Config, procedural_config
from level.procedural import (
    PhaseConstraints,
    ProceduralPlatformingGenerator,
    load_phases,
)
from level.procedural._clearance import floor_clearance_height
from level.sketch.platforming_limits import (
    compute_platforming_limits,
    delver_height_tiles,
    jump_height_tiles,
    max_gap_tiles_for_delta_height,
)
from level.sketch.schema import parse_level_sketch


class TestDeltaGapLimits(unittest.TestCase):
    def test_same_height_matches_recommended_max_gap(self):
        limits = compute_platforming_limits()
        self.assertEqual(
            max_gap_tiles_for_delta_height(0),
            limits.recommended_max_gap_tiles,
        )

    def test_climb_shrinks_or_equals_same_height_gap(self):
        same = max_gap_tiles_for_delta_height(0)
        climb = max_gap_tiles_for_delta_height(2)
        self.assertLessEqual(climb, same)

    def test_fall_can_widen_gap(self):
        same = max_gap_tiles_for_delta_height(0)
        fall = max_gap_tiles_for_delta_height(-3)
        self.assertGreaterEqual(fall, same)

    def test_unreachable_climb_returns_zero(self):
        jh = jump_height_tiles()
        self.assertEqual(max_gap_tiles_for_delta_height(jh + 5), 0)

    def test_delver_and_jump_height_helpers(self):
        limits = compute_platforming_limits()
        self.assertEqual(delver_height_tiles(), limits.delver_height_tiles)
        self.assertEqual(jump_height_tiles(), limits.recommended_max_rise_tiles)
        self.assertGreaterEqual(delver_height_tiles(), 1)


class TestClearanceGenerator(unittest.TestCase):
    def test_generate_sketch_is_valid(self):
        gen = ProceduralPlatformingGenerator(
            seed=7,
            phase=PhaseConstraints(name="flat_run", allow_pits=False, allow_floor_height_shifts=False),
        )
        sketch = gen.generate_sketch("Gen_test_01", difficulty=0.5)
        self.assertEqual(sketch.name, "Gen_test_01")
        self.assertGreaterEqual(sketch.width, 6)
        self.assertGreaterEqual(sketch.height, 6)

        delvers = goals = platforms = 0
        for row in sketch.cells:
            for cell in row:
                if "delver" in cell:
                    delvers += 1
                if "goal" in cell:
                    goals += 1
                if "platform" in cell:
                    platforms += 1
        self.assertEqual(delvers, 1)
        self.assertEqual(goals, 1)
        self.assertGreaterEqual(platforms, 4)

    def test_easy_phase_has_floor_clearance_budget(self):
        limits = compute_platforming_limits()
        dh = limits.delver_height_tiles
        expected = floor_clearance_height(delver_height=dh)
        gen = ProceduralPlatformingGenerator(
            seed=1,
            limits=limits,
            phase=PhaseConstraints(
                name="flat_run",
                allow_pits=False,
                allow_floor_height_shifts=False,
                min_path_steps=3,
                max_path_steps=5,
            ),
        )
        self.assertGreaterEqual(gen.floor_clearance_h, expected)
        sketch = gen.generate_sketch("clearance_check")
        self.assertGreaterEqual(sketch.width, 6)

    def test_same_height_pits_respect_gap_cache(self):
        limits = compute_platforming_limits()
        phys_gap = max_gap_tiles_for_delta_height(0)
        gen = ProceduralPlatformingGenerator(
            seed=11,
            limits=limits,
            phase=PhaseConstraints(
                name="same_height_pits",
                allow_pits=True,
                allow_floor_height_shifts=False,
                force_delta_h=0,
                max_gap_tiles=phys_gap,
                min_path_steps=4,
                max_path_steps=8,
            ),
        )
        self.assertEqual(gen.max_gap_for_delta(0), phys_gap)
        sketch = gen.generate_sketch("pits_check")
        parse_level_sketch(
            {
                "name": sketch.name,
                "grid_size": [sketch.width, sketch.height],
                "cells": [
                    [list(cell) if cell else None for cell in row]
                    for row in sketch.cells
                ],
            }
        )

    def test_sketch_dict_round_trips_parser(self):
        gen = ProceduralPlatformingGenerator(seed=1)
        raw = gen.generate_sketch_dict("roundtrip", difficulty=0.3)
        parsed = parse_level_sketch(raw)
        self.assertEqual(parsed.name, "roundtrip")

    def test_curriculum_phases_load(self):
        phases = load_phases()
        names = [p.name for p in phases]
        self.assertIn("flat_run", names)
        self.assertIn("mixed", names)

    def test_finalize_fills_exterior_not_corridor(self):
        gen = ProceduralPlatformingGenerator(
            seed=3,
            phase=PhaseConstraints(
                name="mixed",
                allow_pits=True,
                allow_floor_height_shifts=True,
                min_path_steps=6,
                max_path_steps=10,
            ),
        )
        sketch = gen.generate_sketch("fill_check")
        # Perimeter must be solid; interior should not be mostly empty.
        for x in range(sketch.width):
            self.assertIn("platform", sketch.cells[0][x])
            self.assertIn("platform", sketch.cells[sketch.height - 1][x])
        platforms = sum(
            1 for row in sketch.cells for cell in row if "platform" in cell
        )
        total = sketch.width * sketch.height
        self.assertGreater(platforms / total, 0.35)

    def test_switchbacks_can_reverse_direction(self):
        from level.procedural import path_has_direction_change
        from level.procedural._structures import FloorSeg, PathHead, paint_floor_run, try_switchback
        from level.procedural._sketch_grid import SketchGrid

        # Turn arounds are currently disabled by default per configuration.
        gen = ProceduralPlatformingGenerator(seed=0)
        self.assertEqual(float(gen.cfg.SWITCHBACK_WEIGHT), 0.0)
        self.assertEqual(float(gen.cfg.TURN_WEIGHT), 0.0)

        # Verify low-level try_switchback function works when invoked directly.
        grid = SketchGrid()
        start = paint_floor_run(grid, x0=0, x1=4, floor_y=10, clearance_h=3)
        head = PathHead(1, start, None)
        result = try_switchback(
            grid,
            head,
            climb_delta=2,
            length=3,
            continue_length=4,
            clearance_h=3,
            span_clearance_h=5,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.direction, -1)


    def test_span_clearance_is_takeoff_anchored(self):
        from level.procedural._clearance import paint_span_clearance, span_ceiling_y
        from level.procedural._sketch_grid import CellKind, SketchGrid

        grid = SketchGrid()
        # Higher takeoff at y=10 [0,4), lower landing at y=14 [8,12).
        for x in range(0, 4):
            grid.paint_platform(x, 10)
        for x in range(8, 12):
            grid.paint_platform(x, 14)
        span_h = 7  # JH+DH style
        floor_h = 3
        paint_span_clearance(
            grid,
            takeoff_x0=0,
            takeoff_x1=4,
            takeoff_y=10,
            land_x0=8,
            land_x1=12,
            land_y=14,
            height=span_h,
            floor_clearance_h=floor_h,
            landing_edge_overlap=1,
            requires_jump=True,
        )
        ceiling = span_ceiling_y(takeoff_y=10, span_height=span_h)
        # Gap keeps the takeoff vault open.
        self.assertEqual(grid.get(6, ceiling), CellKind.CLEARANCE)
        # Landing stays ambient (no post-edge vault).
        self.assertNotEqual(grid.get(9, ceiling), CellKind.CLEARANCE)
        self.assertEqual(grid.get(9, 14 - floor_h), CellKind.CLEARANCE)
        # Farther above ambient on landing must not be forced empty by the vault.
        self.assertNotEqual(grid.get(11, ceiling), CellKind.CLEARANCE)

    def test_climb_raises_landing_lip_only(self):
        from level.procedural._clearance import paint_span_clearance, span_ceiling_y
        from level.procedural._sketch_grid import CellKind, SketchGrid

        grid = SketchGrid()
        # Lower takeoff y=14 [0,4), higher landing y=10 [4,10).
        for x in range(0, 4):
            grid.paint_platform(x, 14)
        for x in range(4, 10):
            grid.paint_platform(x, 10)
        span_h = 10
        floor_h = 3
        paint_span_clearance(
            grid,
            takeoff_x0=3,
            takeoff_x1=4,
            takeoff_y=14,
            land_x0=4,
            land_x1=10,
            land_y=10,
            height=span_h,
            floor_clearance_h=floor_h,
            landing_edge_overlap=1,
            requires_jump=True,
        )
        ceiling = span_ceiling_y(takeoff_y=14, span_height=span_h)
        # Lip (x=4) meets takeoff ceiling; far landing (x=9) stays ambient.
        self.assertEqual(grid.get(4, ceiling), CellKind.CLEARANCE)
        self.assertNotEqual(grid.get(9, ceiling), CellKind.CLEARANCE)
        self.assertEqual(grid.get(9, 10 - floor_h), CellKind.CLEARANCE)

    def test_contiguous_drop_skips_jump_vault(self):
        from level.procedural._clearance import paint_span_clearance, span_ceiling_y
        from level.procedural._sketch_grid import CellKind, SketchGrid

        grid = SketchGrid()
        for x in range(0, 4):
            grid.paint_platform(x, 10)
        for x in range(4, 8):
            grid.paint_platform(x, 14)
        floor_h = 3
        paint_span_clearance(
            grid,
            takeoff_x0=3,
            takeoff_x1=4,
            takeoff_y=10,
            land_x0=4,
            land_x1=8,
            land_y=14,
            height=7,
            floor_clearance_h=floor_h,
            requires_jump=False,
        )
        ceiling = span_ceiling_y(takeoff_y=10, span_height=7)
        self.assertNotEqual(grid.get(3, ceiling), CellKind.CLEARANCE)
        self.assertEqual(grid.get(3, 10 - floor_h), CellKind.CLEARANCE)
        self.assertEqual(grid.get(5, 14 - floor_h), CellKind.CLEARANCE)

    def test_clearance_height_continuity_respects_max_step(self):
        from level.procedural._clearance import ClearanceHeightState
        from level.config import procedural_config
        import random

        rng = random.Random(0)
        state = ClearanceHeightState.from_config(
            delver_height=3, cfg=procedural_config, rng=rng
        )
        prev = state.current
        for _ in range(40):
            nxt = state.sample_next(rng)
            self.assertLessEqual(abs(nxt - prev), state.max_step)
            self.assertGreaterEqual(nxt, state.min_h)
            self.assertLessEqual(nxt, state.max_h)
            prev = nxt

    def test_multiple_random_seeds_produce_valid_sketches(self):
        limits = compute_platforming_limits()
        for seed in range(10):
            gen = ProceduralPlatformingGenerator(seed=seed, limits=limits)
            sketch_dict = gen.generate_sketch_dict(f"seed_test_{seed}")
            parsed = parse_level_sketch(sketch_dict)
            self.assertEqual(parsed.name, f"seed_test_{seed}")
            self.assertGreaterEqual(parsed.width, 6)
            self.assertGreaterEqual(parsed.height, 6)

            delvers = goals = platforms = 0
            for y, row in enumerate(parsed.cells):
                for x, cell in enumerate(row):
                    if "delver" in cell:
                        delvers += 1
                    if "goal" in cell:
                        goals += 1
                    if "platform" in cell:
                        platforms += 1

            self.assertEqual(delvers, 1, f"Seed {seed} must have exactly 1 Delver")
            self.assertEqual(goals, 1, f"Seed {seed} must have exactly 1 Goal")
            self.assertGreaterEqual(platforms, 10, f"Seed {seed} must have platforms")

            # Verify perimeter is solid
            for x in range(parsed.width):
                self.assertIn("platform", parsed.cells[0][x])
                self.assertIn("platform", parsed.cells[parsed.height - 1][x])
            for y in range(parsed.height):
                self.assertIn("platform", parsed.cells[y][0])
                self.assertIn("platform", parsed.cells[y][parsed.width - 1])

    def test_pit_gaps_stay_open_in_finalized_sketch(self):
        gen = ProceduralPlatformingGenerator(
            seed=5,
            phase=PhaseConstraints(
                name="same_height_pits",
                allow_pits=True,
                allow_floor_height_shifts=False,
                force_delta_h=0,
                min_path_steps=5,
                max_path_steps=8,
            ),
        )
        sketch = gen.generate_sketch("pit_open_check")
        # Ensure there exists at least one column with a pit gap (air down to near bottom wall)
        has_pit_gap_column = False
        for x in range(1, sketch.width - 1):
            # Check if column x is a pit gap: empty air extending to bottom inner row
            if "platform" not in sketch.cells[sketch.height - 2][x]:
                has_pit_gap_column = True
                break
        self.assertTrue(has_pit_gap_column, "Finalized sketch must retain open pit gaps")

    def test_climb_shift_keeps_area_under_landing_solid(self):
        from level.procedural._clearance import paint_span_clearance
        from level.procedural._sketch_grid import CellKind, SketchGrid

        grid = SketchGrid()
        # Lower takeoff y=10 [0,4), higher contiguous landing y=6 [4,10).
        for x in range(0, 4):
            grid.paint_platform(x, 10)
        for x in range(4, 10):
            grid.paint_platform(x, 6)
        paint_span_clearance(
            grid,
            takeoff_x0=2,
            takeoff_x1=4,
            takeoff_y=10,
            land_x0=4,
            land_x1=10,
            land_y=6,
            height=3,
            floor_clearance_h=3,
            landing_edge_overlap=1,
            requires_jump=False,
        )
        # Cells at or below the landing surface must not be cleared, otherwise
        # exterior fill leaves a hidden air pocket under the climb slab.
        for x in range(4, 10):
            for y in range(6, 11):
                self.assertNotEqual(
                    grid.get(x, y),
                    CellKind.CLEARANCE,
                    f"Cell (x={x}, y={y}) under the climb landing must stay solid",
                )

    def test_pit_span_carves_exactly_the_gap_columns(self):
        from level.procedural._finalize import finalize_sketch_dict
        from level.procedural._sketch_grid import SketchGrid
        from level.procedural._structures import (
            PathHead,
            paint_floor_run,
            try_pit,
        )

        grid = SketchGrid()
        start = paint_floor_run(grid, x0=0, x1=5, floor_y=10, clearance_h=3)
        self.assertIsNotNone(start)
        head = PathHead(1, start, None, clearance_h=3)
        landed = try_pit(
            grid,
            head,
            gap=4,
            delta_h=0,
            landing_width=4,
            clearance_h=3,
            span_clearance_h=7,
            span_edge_overlap=2,
        )
        self.assertIsNotNone(landed)
        result = finalize_sketch_dict(
            grid,
            name="pit_align",
            start_seg=start,
            end_seg=landed.segment,
            pad_tiles=2,
            top_margin_tiles=1,
        )
        cells = result["cells"]
        width, height = result["grid_size"]

        def is_platform(x: int, y: int) -> bool:
            cell = cells[y][x]
            return bool(cell) and "platform" in cell

        # Sketch origin: min_x=0, pad=2 → local_x = sketch_x + 3.
        # Floor sketch y=10 → local row 11; gap columns sketch 5..8 → local 8..11.
        floor_row = 11
        self.assertTrue(all(is_platform(x, floor_row) for x in range(3, 8)))
        self.assertTrue(all(is_platform(x, floor_row) for x in range(12, 16)))
        self.assertFalse(any(is_platform(x, floor_row) for x in range(8, 12)))
        # Takeoff lip (local x=7) and landing edge (local x=12) stay solid below.
        for x in (7, 12):
            for y in range(floor_row + 1, height - 1):
                self.assertTrue(
                    is_platform(x, y),
                    f"Edge column x={x} must be solid below the floor (y={y})",
                )
        # The four gap columns (local 8..11) stay open down to the bottom wall.
        for x in range(8, 12):
            for y in range(floor_row + 1, height - 1):
                self.assertFalse(
                    is_platform(x, y),
                    f"Gap column x={x} must stay open below the floor (y={y})",
                )
        _ = width

    def test_no_floating_platform_tiles_across_seeds(self):
        # A platform tile with air directly above and below is a floating slab:
        # it only appears via the takeoff-lip pit carve or climb-shift pockets.
        for seed in range(15):
            gen = ProceduralPlatformingGenerator(seed=seed)
            sketch = gen.generate_sketch(f"float_check_{seed}")
            cells = sketch.cells
            for y in range(1, sketch.height - 1):
                for x in range(1, sketch.width - 1):
                    cell = cells[y][x]
                    if not (cell and "platform" in cell):
                        continue
                    above = cells[y - 1][x]
                    below = cells[y + 1][x]
                    above_air = not above or "platform" not in above
                    below_air = not below or "platform" not in below
                    self.assertFalse(
                        above_air and below_air,
                        f"Floating platform tile at (x={x}, y={y}) in seed {seed}",
                    )

    def test_floor_height_shift_has_no_missing_edge_tip_tiles(self):
        # Test height shifts across 10 random seeds for hollow holes in platform surfaces
        for seed in range(10):
            gen = ProceduralPlatformingGenerator(
                seed=seed,
                phase=PhaseConstraints(
                    name="falls",
                    allow_pits=False,
                    allow_floor_height_shifts=True,
                    min_path_steps=6,
                    max_path_steps=10,
                ),
            )
            sketch = gen.generate_sketch(f"shift_check_{seed}")
            cells = sketch.cells
            for y in range(1, sketch.height - 2):
                for x in range(1, sketch.width - 2):
                    is_left_platform = "platform" in cells[y][x - 1]
                    is_current_empty = "platform" not in cells[y][x]
                    is_right_platform = "platform" in cells[y][x + 1]
                    is_below_platform = "platform" in cells[y + 1][x]

                    is_above_platform = "platform" in cells[y - 1][x]
                    if (
                        is_left_platform
                        and is_current_empty
                        and is_right_platform
                        and is_below_platform
                        and is_above_platform
                    ):
                        self.fail(
                            f"Found missing surface tile at (x={x}, y={y}) in seed {seed}"
                        )

    def test_fall_edges_have_unblocked_passage_clearance(self):
        # Verify that for a fall edge, full Delver height (3 tiles) above the takeoff surface
        # extends at least 2 columns past the edge into the drop zone.
        for seed in range(5):
            gen = ProceduralPlatformingGenerator(
                seed=seed,
                phase=PhaseConstraints(
                    name="falls",
                    allow_pits=False,
                    allow_floor_height_shifts=True,
                    min_path_steps=5,
                    max_path_steps=8,
                ),
            )
            sketch = gen.generate_sketch(f"passage_check_{seed}")
            cells = sketch.cells
            for y in range(1, sketch.height - 4):
                for x in range(1, sketch.width - 3):
                    # For a true fall edge, the landing platform sits at a lower row (y_land > y)
                    is_exposed_surface = (
                        "platform" in cells[y][x] and "platform" not in cells[y - 1][x]
                    )
                    if is_exposed_surface and "platform" not in cells[y][x + 1]:
                        has_lower_landing = any(
                            "platform" in cells[ly][x + 1] or "platform" in cells[ly][x + 2]
                            for ly in range(y + 1, sketch.height - 1)
                        )
                        has_higher_landing = any(
                            "platform" in cells[hy][x + 1] or "platform" in cells[hy][x + 2]
                            for hy in range(1, y)
                        )
                        if has_lower_landing and not has_higher_landing:
                            # The 2 columns after the edge must be open for at least 3 tiles ABOVE y (y-1, y-2, y-3)
                            for dx in (1, 2):
                                for dy in (1, 2, 3):
                                    air_cell = cells[y - dy][x + dx]
                                    self.assertNotIn(
                                        "platform",
                                        air_cell,
                                        f"Ceiling block at (x={x+dx}, y={y-dy}) blocks fall edge from (x={x}, y={y}) in seed {seed}",
                                    )

    def test_deep_drop_clearance_scales_with_drop_depth(self):
        from level.procedural._clearance import paint_span_clearance
        from level.procedural._sketch_grid import CellKind, SketchGrid

        grid = SketchGrid()
        for x in range(0, 4):
            grid.paint_platform(x, 10)
        for x in range(4, 10):
            grid.paint_platform(x, 14)  # 4-tile drop

        paint_span_clearance(
            grid,
            takeoff_x0=0,
            takeoff_x1=4,
            takeoff_y=10,
            land_x0=4,
            land_x1=10,
            land_y=14,
            height=3,
            floor_clearance_h=3,
            landing_edge_overlap=2,
            requires_jump=False,
        )
        # For a 4-tile drop, clearance up to takeoff ceiling (row 7 = 10-3) must span at least 4 columns into landing (x=4, 5, 6, 7)
        for x in range(4, 8):
            self.assertEqual(
                grid.get(x, 7),
                CellKind.CLEARANCE,
                f"Column {x} at ceiling row 7 should be CLEARANCE for deep drop",
            )


class TestTravelDirectionBias(unittest.TestCase):
    """ltr_direction_bias in [-1, 1]: +1 forces LTR, -1 forces RTL, 0 is 50/50."""

    @staticmethod
    def _cfg_with_bias(bias: float) -> Config:
        return Config({**procedural_config.as_dict(), "ltr_direction_bias": bias})

    @staticmethod
    def _actor_column(sketch, label: str) -> int:
        for row in sketch.cells:
            for x, cell in enumerate(row):
                if cell and label in cell:
                    return x
        raise AssertionError(f"No '{label}' cell found in sketch")

    def test_bias_extremes_force_orientation(self):
        for bias, expect_ltr in ((1.0, True), (-1.0, False)):
            cfg = self._cfg_with_bias(bias)
            for seed in range(8):
                gen = ProceduralPlatformingGenerator(seed=seed, cfg=cfg)
                sketch = gen.generate_sketch(f"bias_{bias}_{seed}")
                delver_x = self._actor_column(sketch, "delver")
                goal_x = self._actor_column(sketch, "goal")
                if expect_ltr:
                    self.assertLess(
                        delver_x, goal_x, f"seed {seed} must run left-to-right"
                    )
                else:
                    self.assertGreater(
                        delver_x, goal_x, f"seed {seed} must run right-to-left"
                    )

    def test_bias_zero_yields_both_orientations(self):
        cfg = self._cfg_with_bias(0.0)
        orientations: set[bool] = set()
        for seed in range(20):
            gen = ProceduralPlatformingGenerator(seed=seed, cfg=cfg)
            sketch = gen.generate_sketch(f"bias0_{seed}")
            delver_x = self._actor_column(sketch, "delver")
            goal_x = self._actor_column(sketch, "goal")
            orientations.add(delver_x < goal_x)
        self.assertEqual(orientations, {True, False})

    def test_rtl_levels_satisfy_layout_invariants(self):
        cfg = self._cfg_with_bias(-1.0)
        for seed in range(15):
            gen = ProceduralPlatformingGenerator(seed=seed, cfg=cfg)
            sketch = gen.generate_sketch(f"rtl_check_{seed}")
            cells = sketch.cells

            delvers = goals = 0
            for row in cells:
                for cell in row:
                    if cell and "delver" in cell:
                        delvers += 1
                    if cell and "goal" in cell:
                        goals += 1
            self.assertEqual(delvers, 1, f"seed {seed}")
            self.assertEqual(goals, 1, f"seed {seed}")

            for x in range(sketch.width):
                self.assertIn("platform", cells[0][x])
                self.assertIn("platform", cells[sketch.height - 1][x])
            for y in range(sketch.height):
                self.assertIn("platform", cells[y][0])
                self.assertIn("platform", cells[y][sketch.width - 1])

            for y in range(1, sketch.height - 1):
                for x in range(1, sketch.width - 1):
                    cell = cells[y][x]
                    if not (cell and "platform" in cell):
                        continue
                    above = cells[y - 1][x]
                    below = cells[y + 1][x]
                    above_air = not above or "platform" not in above
                    below_air = not below or "platform" not in below
                    self.assertFalse(
                        above_air and below_air,
                        f"Floating platform tile at (x={x}, y={y}) in RTL seed {seed}",
                    )


if __name__ == "__main__":
    unittest.main()
