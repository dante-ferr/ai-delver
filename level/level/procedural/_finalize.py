"""Crop, seal, fill unreachable exterior, and place delver / goal / hazards."""

from __future__ import annotations

import random
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
    pit_depth_range: tuple[int, int] = (1, 5),
    spike_group_range: tuple[int, int] = (2, 6),
    ceiling_gallery_raise: int = 2,
    ceiling_spike_odds: float = 0.6,
    wall_spike_odds: float = 1.0,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Build a dense sketch dict with walls, exterior fill, actors, and hazards.

    Only the carved path corridor stays empty: painted clearance plus the air
    cell immediately above each floor. Every other interior cell becomes a
    platform so dead space around the path is filled solid.

    Pit gaps become spike-floored shafts: open air down to a sampled depth
    (``pit_depth_range``, measured below the lower floor edge), then a flat
    full-width row of spike traps on solid ground (extremity corner cells
    included — they point up with the row). Pit internal walls stay clean.

    Decorative spikes are applied to surfaces in open air — never embedded in
    rock — and only where the Delver never needs to touch. The painted
    clearance is the movement envelope: it provably contains the body during
    required traversal (walking corridors are ≥ Delver height; jump vaults
    are ≥ jump apex + body). So ceiling strips hang from *gallery* ceilings
    raised ``ceiling_gallery_raise`` rows strictly above each stretch's own
    envelope, which keeps spikes untouchable during required movement at any
    corridor height; only optional jumps can reach them. Strip lengths are
    sampled from ``spike_group_range`` so spikes appear grouped, and wall
    spikes may mount the raised gallery end walls above the envelope.
    Internal corners never show spikes on both adjoining surfaces: 4-adjacent
    spikes always share one orientation.

    ``travel_direction`` is +1 for left-to-right levels, -1 for right-to-left;
    it only selects which end of the start/goal segments the actors anchor at.
    """
    rng = rng if rng is not None else random.Random(0)
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

    # Pit gaps (columns explicitly registered by try_pit during generation)
    # become spike-floored shafts. Translate with the same +1 wall offset as
    # to_local, else the span shifts one column left and carves under the
    # takeoff lip / misses the last gap column.
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

    min_depth, max_depth = pit_depth_range
    min_depth = max(1, int(min_depth))
    max_depth = max(min_depth, int(max_depth))

    spikes: set[tuple[int, int]] = set()

    for span in spans:
        # Adjacent exposed floor rows on both lips of the span.
        edge_ys = [
            py for x in span
            for (px, py) in platforms
            if abs(px - x) <= 2 and (px, py - 1) not in platforms
        ]
        if not edge_ys:
            continue
        higher_y = min(edge_ys)
        lower_y = max(edge_ys)
        depth = rng.randint(min_depth, max_depth)

        # One flat spike row per span, below the lower lip (the jump arc never
        # reaches it) and above the first existing platform below the edge.
        first_platform_below = min(
            (
                y
                for x in span
                for y in range(lower_y + 1, height - 1)
                if (x, y) in platforms
            ),
            default=None,
        )
        spike_row = min(lower_y + depth, height - 2)
        if first_platform_below is not None:
            spike_row = min(spike_row, first_platform_below - 1)
        if spike_row < lower_y + 1:
            continue  # blocked immediately below the edge; leave solid

        for x in span:
            for y in range(higher_y + 1, spike_row):
                pos = (x, y)
                platforms.discard(pos)
                playable_air.add(pos)
            spike = (x, spike_row)
            platforms.discard(spike)
            playable_air.discard(spike)
            spikes.add(spike)

    # Fill every interior cell that is not part of the carved corridor.
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            pos = (x, y)
            if pos in platforms or pos in playable_air or pos in spikes:
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
    actor_footprints: set[tuple[int, int]] = set()
    for anchor, size in ((delver_anchor, delver_size), (goal_anchor, goal_size)):
        footprint = _footprint(anchor, size)
        actor_footprints |= footprint
        for cell in footprint:
            platforms.discard(cell)

    # Any spike left without an adjacent platform master (e.g. floating over a
    # lower corridor passing beneath a pit) collapses into solid rock instead.
    for spike in list(spikes):
        if not _master_directions(spike, platforms):
            spikes.discard(spike)
            platforms.add(spike)

    _place_spike_galleries(
        platforms=platforms,
        playable_air=playable_air,
        spikes=spikes,
        width=width,
        height=height,
        delver_anchor=delver_anchor,
        delver_size=delver_size,
        goal_anchor=goal_anchor,
        goal_size=goal_size,
        spike_group_range=spike_group_range,
        ceiling_gallery_raise=ceiling_gallery_raise,
        ceiling_spike_odds=ceiling_spike_odds,
        wall_spike_odds=wall_spike_odds,
        rng=rng,
    )

    cells: list[list[Any]] = [[None for _ in range(width)] for _ in range(height)]
    for px, py in platforms:
        if 0 <= px < width and 0 <= py < height:
            cells[py][px] = "platform"

    for sx, sy in spikes:
        if 0 <= sx < width and 0 <= sy < height:
            cells[sy][sx] = "spike_trap"

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


def _master_directions(
    pos: tuple[int, int], platforms: set[tuple[int, int]]
) -> set[tuple[int, int]]:
    """Directions of platform cells adjacent to ``pos`` (an AttachedTile's masters)."""
    x, y = pos
    return {
        d
        for d in ((0, -1), (0, 1), (-1, 0), (1, 0))
        if (x + d[0], y + d[1]) in platforms
    }


def _place_spike_galleries(
    *,
    platforms: set[tuple[int, int]],
    playable_air: set[tuple[int, int]],
    spikes: set[tuple[int, int]],
    width: int,
    height: int,
    delver_anchor: tuple[int, int],
    delver_size: tuple[int, int],
    goal_anchor: tuple[int, int],
    goal_size: tuple[int, int],
    spike_group_range: tuple[int, int],
    ceiling_gallery_raise: int,
    ceiling_spike_odds: float,
    wall_spike_odds: float,
    rng: random.Random,
) -> None:
    """Raise ceilings into galleries above the movement envelope; apply strips.

    The contiguous open air above an exposed floor is the painted movement
    envelope: by construction it contains the Delver's body during required
    traversal (walking corridors are ≥ Delver height; jump vaults are ≥ jump
    apex + body). A gallery therefore carves ``ceiling_gallery_raise`` rows
    strictly above the *highest* envelope top of its run and hangs a grouped
    spike strip from the raised ceiling — untouchable during required
    movement at any corridor height, reachable only by optional jumps. Wall
    spikes may mount the gallery end walls on the rows between the envelope
    top and the strip. Internal corners never show spikes on both adjoining
    surfaces: every placed spike has exactly one platform master orientation.
    """
    if ceiling_spike_odds <= 0.0 and wall_spike_odds <= 0.0:
        return

    raise_rows = max(1, int(ceiling_gallery_raise))
    g_min, g_max = spike_group_range
    g_min = max(1, int(g_min))
    g_max = max(g_min, int(g_max))

    open_air = playable_air - platforms - spikes

    actor_columns: set[int] = set()
    for anchor, size in ((delver_anchor, delver_size), (goal_anchor, goal_size)):
        ax, _ = anchor
        fw, _ = size
        actor_columns.update(range(ax - 1, ax + fw + 1))

    # Candidate columns: an exposed floor with its open-air envelope above.
    # eligible[x] = (floor_y, envelope_top).
    eligible: dict[int, tuple[int, int]] = {}
    for x in range(1, width - 1):
        if x in actor_columns:
            continue
        for y in range(1, height - 1):
            if (x, y) not in platforms or (x, y - 1) not in open_air:
                continue
            air_h = 0
            while (x, y - 1 - air_h) in open_air:
                air_h += 1
            eligible[x] = (y, y - air_h)
            break  # one gallery floor per column

    # Contiguous runs of eligible columns sharing the same floor row.
    runs: list[list[int]] = []
    for x in sorted(eligible):
        if (
            not runs
            or x > runs[-1][-1] + 1
            or eligible[runs[-1][-1]][0] != eligible[x][0]
        ):
            runs.append([x])
        else:
            runs[-1].append(x)

    # Phase 1: pick galleries and carve their raised ceilings. A gallery spans
    # its strip plus one end column per side, so halls stay snug and strips
    # fill the whole raised ceiling.
    galleries: list[tuple[int, int, int]] = []  # (x0, x1, spike_row)
    for run in runs:
        if len(run) < g_min + 2 or rng.random() >= ceiling_spike_odds:
            continue
        # The strip row clears the tallest envelope in the run by `raise_rows`.
        spike_row = min(eligible[x][1] for x in run) - raise_rows
        if spike_row < 2:
            continue
        carve_rows_by_x = {
            x: range(spike_row, eligible[x][1]) for x in run
        }
        # Every carved cell must be solid rock (never other air), the cap
        # above the strip must be solid, and carving must never steal an
        # existing spike's master.
        if any(
            (x, spike_row - 1) not in platforms
            or any((x, cy) not in platforms for cy in carve_rows_by_x[x])
            or any(
                (nx, ny) in spikes
                for cy in carve_rows_by_x[x]
                for nx, ny in ((x, cy - 1), (x, cy + 1), (x - 1, cy), (x + 1, cy))
            )
            for x in run
        ):
            continue
        length = min(rng.randint(g_min, g_max), len(run) - 2)
        start = rng.randint(0, len(run) - (length + 2))
        gallery = run[start : start + length + 2]
        for x in gallery:
            for cy in carve_rows_by_x[x]:
                platforms.discard((x, cy))
                playable_air.add((x, cy))
        galleries.append((gallery[0], gallery[-1], spike_row))

    # Phase 2: apply strips and end-wall spikes against the final platforms.
    for x0, x1, spike_row in galleries:
        # Strip cells must hang from a lone ceiling master (end columns touch
        # an end wall too — internal corners stay empty).
        strip_cols = [
            x
            for x in range(x0, x1 + 1)
            if _master_directions((x, spike_row), platforms) == {(0, -1)}
        ]
        if not strip_cols:
            continue
        for x in strip_cols:
            cell = (x, spike_row)
            playable_air.discard(cell)
            spikes.add(cell)
        if wall_spike_odds > 0.0:
            for end_x, outward in ((x0, (-1, 0)), (x1, (1, 0))):
                envelope_top = eligible[end_x][1]
                for cy in range(spike_row + 1, envelope_top):
                    cell = (end_x, cy)
                    if cell not in playable_air:
                        continue
                    if _master_directions(cell, platforms) != {outward}:
                        continue
                    if rng.random() < wall_spike_odds:
                        playable_air.discard(cell)
                        spikes.add(cell)

    # Safety net: any spike whose master vanished collapses into solid rock.
    for spike in list(spikes):
        if not _master_directions(spike, platforms):
            spikes.discard(spike)
            platforms.add(spike)


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
