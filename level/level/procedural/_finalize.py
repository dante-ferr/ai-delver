"""Crop, seal, fill unreachable exterior, and place delver / goal."""

from __future__ import annotations

from typing import Any

from level.config import config as level_config
from level.procedural._sketch_grid import CellKind, SketchGrid
from level.procedural._structures import FloorSeg
from level.world_object_sizes import world_object_size


def finalize_sketch_dict(
    grid: SketchGrid,
    *,
    name: str,
    start_seg: FloorSeg,
    end_seg: FloorSeg,
    pad_tiles: int = 2,
    top_margin_tiles: int = 1,
    travel_direction: int = 1,
) -> dict[str, Any]:
    """Build a dense sketch dict with walls, exterior fill, and actors.

    Only the carved path corridor stays empty: painted clearance plus the air
    cell immediately above each floor. Every other interior cell becomes a
    platform so dead space around the path is filled solid.

    ``travel_direction`` is +1 for left-to-right levels, -1 for right-to-left;
    it only selects which end of the start/goal segments the actors anchor at.
    """
    if not grid:
        raise ValueError("Cannot finalize an empty sketch grid.")

    from level.sketch.platforming_limits import compute_platforming_limits
    import math

    limits = compute_platforming_limits()
    bottom_margin_tiles = max(5, math.ceil(limits.max_jump_height_tiles) + 1)

    min_x, min_y, max_x, max_y = grid.bounds()
    # Reserve air above the highest painted cell for clearance / actors.
    min_y -= max(0, int(top_margin_tiles))
    max_y += bottom_margin_tiles
    pad = max(0, int(pad_tiles))

    # Translate so content sits inside a padded interior; +1 later for walls.
    origin_x = min_x - pad
    origin_y = min_y - pad
    inner_w = (max_x - min_x + 1) + 2 * pad
    inner_h = (max_y - min_y + 1) + 2 * pad
    # Outer grid includes perimeter walls.
    width = inner_w + 2
    height = inner_h + 2

    min_w, min_h = tuple(level_config.MIN_GRID_SIZE)
    max_w, max_h = tuple(level_config.MAX_GRID_SIZE)
    width = max(min_w, width)
    height = max(min_h, height)
    if width > max_w or height > max_h:
        raise ValueError(
            f"Generated sketch {width}x{height} exceeds max grid "
            f"{max_w}x{max_h} (pad={pad}, top_margin={top_margin_tiles}). "
            "Reduce path steps, platform widths, or clearance height."
        )

    def to_local(x: int, y: int) -> tuple[int, int]:
        return x - origin_x + 1, y - origin_y + 1

    platforms: set[tuple[int, int]] = set()
    playable_air: set[tuple[int, int]] = set()

    for (gx, gy), kind in grid._cells.items():  # noqa: SLF001 — finalize owns the grid
        lx, ly = to_local(gx, gy)
        if not (0 < lx < width - 1 and 0 < ly < height - 1):
            continue
        if kind == CellKind.PLATFORM:
            platforms.add((lx, ly))
        elif kind == CellKind.CLEARANCE:
            playable_air.add((lx, ly))

    delver_size = world_object_size("delver")
    goal_size = world_object_size("goal")
    reserve_h = max(delver_size[1], goal_size[1], 3)

    # Reserve full standing height for Delver and Goal above every exposed platform floor.
    for px, py in list(platforms):
        if (px, py - 1) not in platforms:
            for dh in range(1, reserve_h + 1):
                air_y = py - dh
                if 0 < air_y < height - 1:
                    if (px, air_y) not in platforms:
                        playable_air.add((px, air_y))

    from level.sketch.platforming_limits import compute_platforming_limits
    import math

    limits = compute_platforming_limits()
    min_pit_depth = max(5, math.ceil(limits.max_jump_height_tiles) + 1)

    # Pit gaps (columns explicitly registered by try_pit during generation)
    # propagate open air down so pits are at least min_pit_depth (JH + 1) tiles deep.
    # Translate with the same +1 wall offset as to_local, else the span shifts
    # one column left and carves under the takeoff lip / misses the last gap column.
    sorted_pit_cols = sorted([
        x - origin_x + 1 for x in grid.pit_columns if 0 < (x - origin_x + 1) < width - 1
    ])

    # Group contiguous pit columns into spans
    spans: list[list[int]] = []
    for x in sorted_pit_cols:
        if not spans or x > spans[-1][-1] + 1:
            spans.append([x])
        else:
            spans[-1].append(x)

    for span in spans:
        # Find adjacent upper floor height for the span
        edge_ys = [
            py for x in span
            for (px, py) in platforms
            if abs(px - x) <= 2 and (px, py - 1) not in platforms
        ]
        if not edge_ys:
            continue
        ref_y = min(edge_ys)
        min_pit_bottom = min(height - 2, ref_y + min_pit_depth)

        # Enforce min_pit_depth (JH + 1) tiles open air below the edge
        for x in span:
            for dy in range(ref_y + 1, min_pit_bottom + 1):
                pos = (x, dy)
                if pos in platforms:
                    platforms.remove(pos)
                playable_air.add(pos)

        # Check if any column in the span has a platform below min_pit_bottom
        span_platforms_below = [
            cy for x in span
            for cy in range(min_pit_bottom + 1, height - 1)
            if (x, cy) in platforms
        ]

        if span_platforms_below:
            pit_floor_y = min(span_platforms_below)
            # Clear open air down to pit_floor_y - 1 and paint uniform pit floor at pit_floor_y
            for x in span:
                for dy in range(min_pit_bottom + 1, pit_floor_y):
                    pos = (x, dy)
                    if pos in platforms:
                        platforms.remove(pos)
                    playable_air.add(pos)
                platforms.add((x, pit_floor_y))
        else:
            # Clear open air all the way down to bottom perimeter wall
            for x in span:
                for dy in range(min_pit_bottom + 1, height - 1):
                    if (x, dy) in platforms:
                        platforms.remove((x, dy))
                    playable_air.add((x, dy))

    # Fill every interior cell that is not part of the carved corridor.
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            pos = (x, y)
            if pos in platforms or pos in playable_air:
                continue
            platforms.add(pos)

    # Perimeter walls.
    for x in range(width):
        platforms.add((x, 0))
        platforms.add((x, height - 1))
    for y in range(height):
        platforms.add((0, y))
        platforms.add((width - 1, y))

    delver_size = world_object_size("delver")
    goal_size = world_object_size("goal")
    start_local = _seg_to_local(start_seg, to_local)
    end_local = _seg_to_local(end_seg, to_local)

    # Anchor actors at the trailing edge of travel: Delver at the spawn edge
    # facing the path, Goal at the far frontier edge of the final segment.
    delver_anchor = _pick_anchor(
        start_local,
        delver_size,
        platforms,
        width,
        height,
        prefer_end=travel_direction < 0,
    )
    goal_anchor = _pick_anchor(
        end_local,
        goal_size,
        platforms,
        width,
        height,
        prefer_end=travel_direction > 0,
        forbidden=_footprint(delver_anchor, delver_size),
    )

    # Reachability flood-fill from Delver spawn to eliminate unreachable interior pockets
    start_cell = (delver_anchor[0], delver_anchor[1])
    queue = [start_cell] if start_cell in playable_air else []
    if not queue:
        for dh in range(1, delver_size[1] + 1):
            cell = (delver_anchor[0], delver_anchor[1] - dh)
            if cell in playable_air:
                queue.append(cell)
                break

    visited = set(queue)
    reachable_air: set[tuple[int, int]] = set()
    while queue:
        cx, cy = queue.pop(0)
        reachable_air.add((cx, cy))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = cx + dx, cy + dy
            if 0 < nx < width - 1 and 0 < ny < height - 1:
                ncell = (nx, ny)
                if ncell in playable_air and ncell not in platforms and ncell not in visited:
                    visited.add(ncell)
                    queue.append(ncell)

    # Convert all unreachable interior air pockets into solid platform blocks
    unreachable_pockets = playable_air - reachable_air
    for pos in unreachable_pockets:
        platforms.add(pos)

    # Carve platforms out of actor footprints.
    for anchor, size in ((delver_anchor, delver_size), (goal_anchor, goal_size)):
        for cell in _footprint(anchor, size):
            platforms.discard(cell)

    cells: list[list[Any]] = [[None for _ in range(width)] for _ in range(height)]
    for px, py in platforms:
        if 0 <= px < width and 0 <= py < height:
            cells[py][px] = "platform"

    for anchor, label in ((delver_anchor, "delver"), (goal_anchor, "goal")):
        ax, ay = anchor
        if not (0 <= ax < width and 0 <= ay < height):
            raise ValueError(
                f"Actor '{label}' anchor {anchor} is outside grid {width}x{height}."
            )
        cells[ay][ax] = label

    return {
        "name": name,
        "grid_size": [width, height],
        "cells": cells,
    }


def _seg_to_local(
    seg: FloorSeg, to_local
) -> FloorSeg:
    sx0, sy = to_local(seg.x0, seg.y)
    sx1, _ = to_local(seg.x1 - 1, seg.y)
    return FloorSeg(sx0, sx1 + 1, sy)


def _footprint(anchor: tuple[int, int], size: tuple[int, int]) -> set[tuple[int, int]]:
    from pytiling import footprint_positions

    return set(footprint_positions(anchor, size))


def _pick_anchor(
    seg: FloorSeg,
    size: tuple[int, int],
    platforms: set[tuple[int, int]],
    width: int,
    height: int,
    *,
    prefer_end: bool = False,
    forbidden: set[tuple[int, int]] | None = None,
) -> tuple[int, int]:
    """Pick a bottom-left actor anchor standing on ``seg`` (or any nearby floor)."""
    forbidden = forbidden or set()
    fw, fh = size

    def _try_xs(xs: list[int], floor_y: int) -> tuple[int, int] | None:
        for ax in xs:
            ay = floor_y - 1
            if ay < 1 or ay + fh - 1 >= height - 1:
                continue
            if ax < 1 or ax + fw - 1 >= width - 1:
                continue
            fps = _footprint((ax, ay), size)
            if fps & forbidden:
                continue
            if fps & platforms:
                continue
            if not all(0 < cx < width - 1 and 0 < cy < height - 1 for cx, cy in fps):
                continue
            # Require floor under the footprint columns.
            if not all((ax + dx, floor_y) in platforms for dx in range(fw)):
                continue
            return (ax, ay)
        return None

    if prefer_end:
        xs = list(range(seg.x1 - fw, seg.x0 - 1, -1))
    else:
        xs = list(range(seg.x0, seg.x1 - fw + 1))
    if not xs:
        xs = [seg.x0]

    found = _try_xs(xs, seg.y)
    if found is not None:
        return found

    # Fallback: only other columns on the same floor segment (never wander mid-map).
    if prefer_end:
        xs_all = list(range(seg.x1 - 1, seg.x0 - 1, -1))
    else:
        xs_all = list(range(seg.x0, seg.x1))
    found = _try_xs(xs_all, seg.y)
    if found is not None:
        return found

    raise ValueError(
        f"Could not place actor footprint {size} on segment "
        f"x=[{seg.x0},{seg.x1}) y={seg.y} within {width}x{height}."
    )
