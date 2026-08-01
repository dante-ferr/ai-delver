"""Paint enforced empty clearance above floors and across pits / height shifts."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from level.procedural._sketch_grid import SketchGrid


def floor_clearance_bounds(
    *,
    delver_height: int,
    min_delver_heights: float = 1.0,
    max_delver_heights: float = 2.5,
) -> tuple[int, int]:
    """Inclusive ``(min_tiles, max_tiles)`` for floor clearance height."""
    lo = max(1, int(math.ceil(delver_height * min_delver_heights)))
    hi = max(lo, int(math.ceil(delver_height * max_delver_heights)))
    return lo, hi


def floor_clearance_height(
    *,
    delver_height: int,
    delver_height_multiplier: float = 1.0,
) -> int:
    """Tiles of empty air required above a floor surface (minimum / legacy helper)."""
    return max(1, int(math.ceil(delver_height * delver_height_multiplier)))


def span_clearance_height(
    *,
    delver_height: int,
    jump_height: int,
    jump_height_multiplier: float = 1.0,
    delver_height_multiplier: float = 1.0,
) -> int:
    """Minimum jump-arc clearance above the **takeoff** floor (JH + DH tiles)."""
    return max(
        1,
        int(
            math.ceil(
                jump_height * jump_height_multiplier
                + delver_height * delver_height_multiplier
            )
        ),
    )


def clearance_height_above_floor(*, floor_y: int, ceiling_y: int) -> int:
    """How many clearance tiles sit between ``floor_y`` (exclusive) and ``ceiling_y`` (inclusive)."""
    return max(0, floor_y - ceiling_y)


def span_ceiling_y(*, takeoff_y: int, span_height: int) -> int:
    """Topmost clearance row (smallest y) measured from the takeoff floor."""
    return takeoff_y - span_height

@dataclass
class ClearanceHeightState:
    """Tracks the active floor-clearance height with continuity constraints."""

    current: int
    min_h: int
    max_h: int
    max_step: int
    stay_weight: float
    change_weight: float

    @classmethod
    def from_config(
        cls,
        *,
        delver_height: int,
        cfg,
        rng: random.Random,
    ) -> "ClearanceHeightState":
        min_mult = float(
            cfg.get(
                "min_floor_clearance_delver_heights",
                cfg.get("floor_clearance_delver_heights", 1.0),
            )
        )
        max_mult = float(
            cfg.get("max_floor_clearance_delver_heights", max(min_mult, 2.5))
        )
        lo, hi = floor_clearance_bounds(
            delver_height=delver_height,
            min_delver_heights=min_mult,
            max_delver_heights=max_mult,
        )
        max_step = max(0, int(cfg.get("clearance_height_max_step", 2)))
        stay = float(cfg.get("clearance_height_stay_weight", 3.0))
        change = float(cfg.get("clearance_height_change_weight", 1.0))
        # Start near the minimum so DH-tall corridors remain common, not exclusive.
        start = lo
        if hi > lo and rng.random() < float(
            cfg.get("clearance_height_start_raise_odds", 0.35)
        ):
            start = rng.randint(lo, min(hi, lo + max_step))
        return cls(
            current=start,
            min_h=lo,
            max_h=hi,
            max_step=max_step,
            stay_weight=stay,
            change_weight=change,
        )

    def sample_next(self, rng: random.Random) -> int:
        """Pick the next floor clearance height, biased to stay near ``current``."""
        lo = max(self.min_h, self.current - self.max_step)
        hi = min(self.max_h, self.current + self.max_step)
        if lo >= hi:
            self.current = lo
            return self.current

        candidates = list(range(lo, hi + 1))
        weights: list[float] = []
        for h in candidates:
            if h == self.current:
                weights.append(max(0.0, self.stay_weight))
            else:
                # Prefer smaller steps when changing.
                step = abs(h - self.current)
                weights.append(max(0.0, self.change_weight) / float(step))
        if sum(weights) <= 0:
            self.current = rng.choice(candidates)
        else:
            self.current = rng.choices(candidates, weights=weights, k=1)[0]
        return self.current

    def raise_to_at_least(self, height: int) -> int:
        """Bump current height up (e.g. after a span) without exceeding max."""
        self.current = min(self.max_h, max(self.current, int(height)))
        return self.current


def paint_floor_clearance(
    grid: SketchGrid,
    *,
    x0: int,
    x1: int,
    floor_y: int,
    height: int,
) -> None:
    """Paint clearance in columns ``[x0, x1)`` for ``height`` tiles above ``floor_y``.

    Sketch y increases downward, so air sits at ``floor_y - 1, floor_y - 2, ...``.
    """
    for x in range(x0, x1):
        for dy in range(1, height + 1):
            grid.paint_clearance(x, floor_y - dy)


def _landing_edge_band(
    *,
    takeoff_x0: int,
    takeoff_x1: int,
    land_x0: int,
    land_x1: int,
    overlap: int,
) -> tuple[int, int]:
    """Landing columns nearest the gap / takeoff face (inclusive-exclusive)."""
    overlap = max(1, int(overlap))
    # Takeoff is to the left of landing.
    if takeoff_x1 <= land_x0:
        return land_x0, min(land_x1, land_x0 + overlap)
    # Takeoff is to the right of landing.
    if land_x1 <= takeoff_x0:
        return max(land_x0, land_x1 - overlap), land_x1
    # Contiguous / overlapping faces: prefer the side toward takeoff centroid.
    takeoff_mid = (takeoff_x0 + takeoff_x1) / 2.0
    land_mid = (land_x0 + land_x1) / 2.0
    if takeoff_mid <= land_mid:
        return land_x0, min(land_x1, land_x0 + overlap)
    return max(land_x0, land_x1 - overlap), land_x1


def paint_span_clearance(
    grid: SketchGrid,
    *,
    takeoff_x0: int,
    takeoff_x1: int,
    takeoff_y: int,
    land_x0: int,
    land_x1: int,
    land_y: int,
    height: int,
    floor_clearance_h: int | None = None,
    landing_edge_overlap: int = 1,
    requires_jump: bool = True,
) -> int:
    """Paint jump / corridor clearance anchored to the **takeoff** floor.

    Jump arcs start on the takeoff edge. The JH+DH vault is therefore measured
    from ``takeoff_y``, painted on the takeoff edge and across gap columns only.

    The landing keeps ambient floor clearance. On climbs (landing higher than
    takeoff), only the lip nearest the gap is raised to meet the takeoff
    ceiling so the arc can clear the edge — the rest of the landing stays low.

    Contiguous drops (``requires_jump=False``) skip the jump vault entirely.

    Returns the clearance height painted on the takeoff edge.
    """
    ambient = (
        int(floor_clearance_h)
        if floor_clearance_h is not None
        else max(1, min(height, 3))
    )

    # Always keep standing room on the full landing.
    paint_floor_clearance(
        grid, x0=land_x0, x1=land_x1, floor_y=land_y, height=ambient
    )

    effective_landing_overlap = max(
        landing_edge_overlap,
        max(0, land_y - takeoff_y),
    )

    if not requires_jump or height < 1:
        higher_y = min(takeoff_y, land_y)
        ceiling = higher_y - ambient
        takeoff_h = max(
            ambient,
            clearance_height_above_floor(floor_y=takeoff_y, ceiling_y=ceiling),
        )
        paint_floor_clearance(
            grid,
            x0=takeoff_x0,
            x1=takeoff_x1,
            floor_y=takeoff_y,
            height=takeoff_h,
        )
        drop_depth = max(0, land_y - takeoff_y)
        effective_landing_overlap = max(landing_edge_overlap, drop_depth)
        lip0, lip1 = _landing_edge_band(
            takeoff_x0=takeoff_x0,
            takeoff_x1=takeoff_x1,
            land_x0=land_x0,
            land_x1=land_x1,
            overlap=effective_landing_overlap,
        )
        # Drop chasm volume only extends past the takeoff edge (not under takeoff platform)
        if takeoff_x1 <= land_x0:
            chasm_x0 = takeoff_x1
            chasm_x1 = max(land_x1, land_x0 + effective_landing_overlap)
        else:
            chasm_x0 = min(land_x0, land_x1 - effective_landing_overlap)
            chasm_x1 = takeoff_x0

        # Never clear at or below the landing surface: for climbs the landing
        # slab is above the takeoff, and carving down to the takeoff level would
        # leave a hidden air pocket under the slab after exterior fill.
        for x in range(chasm_x0, chasm_x1):
            for y in range(ceiling, land_y):
                grid.paint_clearance(x, y)

        lip_h = max(
            ambient,
            clearance_height_above_floor(floor_y=land_y, ceiling_y=ceiling),
        )
        paint_floor_clearance(
            grid, x0=lip0, x1=lip1, floor_y=land_y, height=lip_h
        )
        return takeoff_h

    higher_y = min(takeoff_y, land_y)
    ceiling = higher_y - height
    takeoff_h = max(
        ambient,
        clearance_height_above_floor(floor_y=takeoff_y, ceiling_y=ceiling),
    )
    paint_floor_clearance(
        grid,
        x0=takeoff_x0,
        x1=takeoff_x1,
        floor_y=takeoff_y,
        height=takeoff_h,
    )

    # Gap between the facing edges (empty when the floors are contiguous).
    if takeoff_x1 <= land_x0:
        gap_lo, gap_hi = takeoff_x1, land_x0
    elif land_x1 <= takeoff_x0:
        gap_lo, gap_hi = land_x1, takeoff_x0
    else:
        gap_lo, gap_hi = 0, 0

    from level.sketch.platforming_limits import compute_platforming_limits
    import math

    limits = compute_platforming_limits()
    min_pit_depth = max(5, math.ceil(limits.max_jump_height_tiles) + 1)
    pit_floor = max(takeoff_y, land_y) + min_pit_depth
    for x in range(gap_lo, gap_hi):
        for y in range(ceiling, pit_floor + 1):
            grid.paint_clearance(x, y)

    # Both climbs and drops span vault clearance into the landing edge overlap band.
    lip0, lip1 = _landing_edge_band(
        takeoff_x0=takeoff_x0,
        takeoff_x1=takeoff_x1,
        land_x0=land_x0,
        land_x1=land_x1,
        overlap=landing_edge_overlap,
    )
    lip_h = max(
        ambient,
        clearance_height_above_floor(floor_y=land_y, ceiling_y=ceiling),
    )
    paint_floor_clearance(
        grid, x0=lip0, x1=lip1, floor_y=land_y, height=lip_h
    )

    return takeoff_h
