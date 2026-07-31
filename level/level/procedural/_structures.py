"""Floor continue / pit / floor-height-shift structures for the path generator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from level.procedural._clearance import (
    paint_floor_clearance,
    paint_span_clearance,
)
from level.procedural._sketch_grid import SketchGrid


@dataclass
class FloorSeg:
    """Inclusive-exclusive horizontal floor span on one row (y increases downward)."""

    x0: int
    x1: int
    y: int

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    def tip_x(self, direction: int) -> int:
        """Next column in ``direction`` beyond this segment."""
        return self.x1 if direction > 0 else self.x0 - 1

    def trailing_x(self, direction: int) -> int:
        """Far edge when reversing travel direction."""
        return self.x0 if direction > 0 else self.x1 - 1


@dataclass
class PathHead:
    """Current tip of the growing path."""

    direction: int  # +1 right, -1 left
    segment: FloorSeg
    prev_floor_y: int | None = None
    clearance_h: int = 3

    @property
    def floor_y(self) -> int:
        return self.segment.y

    @property
    def tip_x(self) -> int:
        return self.segment.tip_x(self.direction)


GapLookup = Callable[[int], int]


def can_place_floor_run(
    grid: SketchGrid,
    *,
    x0: int,
    x1: int,
    floor_y: int,
) -> bool:
    """True if every cell in ``[x0, x1)`` at ``floor_y`` may become a platform."""
    if x1 <= x0:
        return False
    for x in range(x0, x1):
        if grid.is_blocked_for_platform(x, floor_y):
            return False
    return True


def paint_floor_run(
    grid: SketchGrid,
    *,
    x0: int,
    x1: int,
    floor_y: int,
    clearance_h: int,
) -> FloorSeg | None:
    if not can_place_floor_run(grid, x0=x0, x1=x1, floor_y=floor_y):
        return None
    for x in range(x0, x1):
        if not grid.paint_platform(x, floor_y):
            return None
    paint_floor_clearance(
        grid, x0=x0, x1=x1, floor_y=floor_y, height=clearance_h
    )
    return FloorSeg(x0, x1, floor_y)


def clearance_height_for_edge(
    *,
    edge_y: int,
    takeoff_y: int,
    span_height: int,
    floor_clearance: int,
) -> int:
    from level.procedural._clearance import (
        clearance_height_above_floor,
        span_ceiling_y,
    )

    ceiling = span_ceiling_y(takeoff_y=takeoff_y, span_height=span_height)
    return max(
        floor_clearance,
        clearance_height_above_floor(floor_y=edge_y, ceiling_y=ceiling),
    )


def try_continue(
    grid: SketchGrid,
    head: PathHead,
    *,
    length: int,
    clearance_h: int,
) -> PathHead | None:
    """Extend the current floor in the travel direction."""
    if length < 1:
        return None
    tip = head.tip_x
    if head.direction > 0:
        x0, x1 = tip, tip + length
    else:
        x0, x1 = tip - length + 1, tip + 1
    seg = paint_floor_run(
        grid, x0=x0, x1=x1, floor_y=head.floor_y, clearance_h=clearance_h
    )
    if seg is None:
        return None
    # Merge with previous if contiguous same height.
    merged = FloorSeg(
        min(head.segment.x0, seg.x0),
        max(head.segment.x1, seg.x1),
        head.floor_y,
    )
    return PathHead(
        head.direction,
        merged,
        head.prev_floor_y,
        clearance_h=clearance_h,
    )


def try_pit(
    grid: SketchGrid,
    head: PathHead,
    *,
    gap: int,
    delta_h: int,
    landing_width: int,
    clearance_h: int,
    span_clearance_h: int,
    span_edge_overlap: int = 1,
) -> PathHead | None:
    """Place a gap then a landing platform with surface delta ``delta_h`` (climb +)."""
    if gap < 1 or landing_width < 1:
        return None
    takeoff_y = head.floor_y
    landing_y = takeoff_y - delta_h  # climb → smaller sketch y
    tip = head.tip_x
    overlap = max(1, int(span_edge_overlap))
    if head.direction > 0:
        gap_x0 = tip
        gap_x1 = tip + gap
        land_x0 = gap_x1
        land_x1 = land_x0 + landing_width
        takeoff_span_x0 = max(head.segment.x0, head.segment.x1 - overlap)
        takeoff_span_x1 = head.segment.x1
    else:
        gap_x1 = tip + 1
        gap_x0 = gap_x1 - gap
        land_x1 = gap_x0
        land_x0 = land_x1 - landing_width
        takeoff_span_x0 = head.segment.x0
        takeoff_span_x1 = min(head.segment.x1, head.segment.x0 + overlap)

    if not can_place_floor_run(grid, x0=land_x0, x1=land_x1, floor_y=landing_y):
        return None

    # Platforms first so span clearance never has to fight missing floors.
    for x in range(land_x0, land_x1):
        if not grid.paint_platform(x, landing_y):
            return None

    paint_span_clearance(
        grid,
        takeoff_x0=takeoff_span_x0,
        takeoff_x1=takeoff_span_x1,
        takeoff_y=takeoff_y,
        land_x0=land_x0,
        land_x1=land_x1,
        land_y=landing_y,
        height=span_clearance_h,
        floor_clearance_h=clearance_h,
        landing_edge_overlap=overlap,
        requires_jump=True,
    )
    # Preserve standing room on the takeoff edge when ambient was already taller.
    paint_floor_clearance(
        grid,
        x0=takeoff_span_x0,
        x1=takeoff_span_x1,
        floor_y=takeoff_y,
        height=max(
            head.clearance_h,
            clearance_height_for_edge(
                edge_y=takeoff_y,
                takeoff_y=takeoff_y,
                span_height=span_clearance_h,
                floor_clearance=clearance_h,
            ),
        ),
    )
    seg = FloorSeg(land_x0, land_x1, landing_y)
    return PathHead(
        head.direction,
        seg,
        prev_floor_y=takeoff_y,
        # Ambient corridor height for continuity — not the span-inflated volume.
        clearance_h=clearance_h,
    )


def try_floor_height_shift(
    grid: SketchGrid,
    head: PathHead,
    *,
    delta_h: int,
    length: int,
    clearance_h: int,
    span_clearance_h: int,
    span_edge_overlap: int = 1,
) -> PathHead | None:
    """Contiguous floor height change (no gap).

    Climbs need a takeoff-anchored jump vault. Contiguous drops do not — the
    Delver walks/falls off the edge, so only ambient floor clearance is kept.
    """
    if length < 1 or delta_h == 0:
        return None
    takeoff_y = head.floor_y
    landing_y = takeoff_y - delta_h
    tip = head.tip_x
    overlap = max(1, int(span_edge_overlap))
    if head.direction > 0:
        x0, x1 = tip, tip + length
        face_x = tip
        takeoff_span_x0 = max(head.segment.x0, head.segment.x1 - overlap)
        takeoff_span_x1 = head.segment.x1
    else:
        x0, x1 = tip - length + 1, tip + 1
        face_x = tip
        takeoff_span_x0 = head.segment.x0
        takeoff_span_x1 = min(head.segment.x1, head.segment.x0 + overlap)

    if not can_place_floor_run(grid, x0=x0, x1=x1, floor_y=landing_y):
        return None

    # Vertical step face between the two surfaces at the transition column.
    lo_y, hi_y = sorted((takeoff_y, landing_y))
    for y in range(lo_y + 1, hi_y):
        if grid.is_blocked_for_platform(face_x, y):
            return None
        if not grid.paint_platform(face_x, y):
            return None

    for x in range(x0, x1):
        if not grid.paint_platform(x, landing_y):
            return None

    requires_jump = delta_h > 0  # climb only
    paint_span_clearance(
        grid,
        takeoff_x0=takeoff_span_x0,
        takeoff_x1=takeoff_span_x1,
        takeoff_y=takeoff_y,
        land_x0=x0,
        land_x1=x1,
        land_y=landing_y,
        height=span_clearance_h,
        floor_clearance_h=clearance_h,
        landing_edge_overlap=overlap,
        requires_jump=requires_jump,
    )
    if requires_jump:
        paint_floor_clearance(
            grid,
            x0=takeoff_span_x0,
            x1=takeoff_span_x1,
            floor_y=takeoff_y,
            height=max(
                head.clearance_h,
                clearance_height_for_edge(
                    edge_y=takeoff_y,
                    takeoff_y=takeoff_y,
                    span_height=span_clearance_h,
                    floor_clearance=clearance_h,
                ),
            ),
        )
    else:
        paint_floor_clearance(
            grid,
            x0=takeoff_span_x0,
            x1=takeoff_span_x1,
            floor_y=takeoff_y,
            height=max(head.clearance_h, clearance_h),
        )
    seg = FloorSeg(x0, x1, landing_y)
    return PathHead(
        head.direction,
        seg,
        prev_floor_y=takeoff_y,
        clearance_h=clearance_h,
    )


def try_turn(head: PathHead) -> PathHead | None:
    """Reverse travel direction when the current floor is higher than the previous."""
    if head.prev_floor_y is None:
        return None
    # Higher = smaller sketch y.
    if head.floor_y >= head.prev_floor_y:
        return None
    return PathHead(
        -head.direction,
        head.segment,
        head.prev_floor_y,
        clearance_h=head.clearance_h,
    )


def can_turn(head: PathHead) -> bool:
    return try_turn(head) is not None


def try_switchback(
    grid: SketchGrid,
    head: PathHead,
    *,
    climb_delta: int,
    length: int,
    continue_length: int,
    clearance_h: int,
    span_clearance_h: int,
    span_edge_overlap: int = 1,
) -> PathHead | None:
    """Climb, reverse direction, then extend the opposite way (forced turn-around)."""
    if climb_delta < 1:
        return None
    climbed = try_floor_height_shift(
        grid,
        head,
        delta_h=climb_delta,
        length=length,
        clearance_h=clearance_h,
        span_clearance_h=span_clearance_h,
        span_edge_overlap=span_edge_overlap,
    )
    if climbed is None:
        return None
    turned = try_turn(climbed)
    if turned is None:
        return climbed
    extended = try_continue(
        grid,
        turned,
        length=max(1, continue_length),
        clearance_h=clearance_h,
    )
    return extended if extended is not None else turned
