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
) -> dict[str, Any]:
    """Build a dense sketch dict with walls, exterior fill, and actors.

    Only the carved path corridor stays empty: painted clearance plus the air
    cell immediately above each floor. Every other interior cell becomes a
    platform so dead space around the path is filled solid.
    """
    if not grid:
        raise ValueError("Cannot finalize an empty sketch grid.")

    min_x, min_y, max_x, max_y = grid.bounds()
    # Reserve air above the highest painted cell for clearance / actors.
    min_y -= max(0, int(top_margin_tiles))
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

    # Standing cell immediately above every platform floor stays empty.
    for px, py in list(platforms):
        above = (px, py - 1)
        if 0 < above[0] < width - 1 and 0 < above[1] < height - 1:
            if above not in platforms:
                playable_air.add(above)

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

    delver_anchor = _pick_anchor(
        start_local, delver_size, platforms, width, height
    )
    goal_anchor = _pick_anchor(
        end_local,
        goal_size,
        platforms,
        width,
        height,
        prefer_end=True,
        forbidden=_footprint(delver_anchor, delver_size),
    )

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
