"""Clearance-aware procedural platforming sketch generator."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

from level.config import procedural_config
from level.procedural._clearance import (
    ClearanceHeightState,
    floor_clearance_height,
    span_clearance_height,
)
from level.procedural._finalize import finalize_sketch_dict
from level.procedural._sketch_grid import SketchGrid
from level.procedural._structures import (
    FloorSeg,
    PathHead,
    can_turn,
    paint_floor_run,
    try_continue,
    try_floor_height_shift,
    try_pit,
    try_switchback,
    try_turn,
)
from level.sketch.platforming_limits import (
    PlatformingLimits,
    compute_platforming_limits,
    max_gap_tiles_for_delta_height,
)
from level.sketch.schema import LevelSketch, parse_level_sketch


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


@dataclass(frozen=True)
class PhaseConstraints:
    """Optional per-phase overrides for structure selection / budgets."""

    name: str = "free"
    allow_pits: bool = True
    allow_floor_height_shifts: bool = True
    max_gap_tiles: int | None = None  # None / 0 → physics for chosen delta
    max_rise_tiles: int | None = None  # None / 0 → jump height
    max_fall_tiles: int | None = None  # None / 0 → config max_fall_height
    force_delta_h: int | None = None
    prefer_positive_delta: bool = False
    prefer_negative_delta: bool = False
    min_path_steps: int | None = None
    max_path_steps: int | None = None
    continue_weight: float | None = None
    pit_weight: float | None = None
    floor_height_shift_weight: float | None = None


class ProceduralPlatformingGenerator:
    """Builds validated level sketches via a growing clearance-aware path."""

    def __init__(
        self,
        seed: int | None = None,
        *,
        limits: PlatformingLimits | None = None,
        phase: PhaseConstraints | None = None,
        cfg: Any | None = None,
    ):
        self.rng = random.Random(seed)
        self.limits = limits or compute_platforming_limits()
        self.phase = phase or PhaseConstraints()
        self.cfg = cfg if cfg is not None else procedural_config

        self.delver_height = int(self.limits.delver_height_tiles)
        self.jump_height = int(self.limits.recommended_max_rise_tiles)
        self.max_fall_height = int(self.cfg.MAX_FALL_HEIGHT)

        # Legacy minimum (Delver height); variable heights use ClearanceHeightState.
        self.floor_clearance_h = floor_clearance_height(
            delver_height=self.delver_height,
            delver_height_multiplier=float(
                self.cfg.get(
                    "min_floor_clearance_delver_heights",
                    self.cfg.get("floor_clearance_delver_heights", 1.0),
                )
            ),
        )
        self.span_clearance_h = span_clearance_height(
            delver_height=self.delver_height,
            jump_height=self.jump_height,
            jump_height_multiplier=float(self.cfg.SPAN_CLEARANCE_JUMP_HEIGHTS),
            delver_height_multiplier=float(self.cfg.SPAN_CLEARANCE_DELVER_HEIGHTS),
        )

    @property
    def physics_max_rise(self) -> int:
        return max(1, self.jump_height)

    @property
    def physics_max_gap(self) -> int:
        return max(1, int(self.limits.recommended_max_gap_tiles))

    def max_gap_for_delta(self, delta_h: int) -> int:
        phys = max_gap_tiles_for_delta_height(delta_h)
        phase_cap = self.phase.max_gap_tiles
        if phase_cap is not None and phase_cap > 0:
            return max(0, min(phys, int(phase_cap)))
        return max(0, phys)

    def rise_budget(self) -> int:
        phase_cap = self.phase.max_rise_tiles
        if phase_cap is not None and phase_cap > 0:
            return min(self.jump_height, int(phase_cap))
        return self.jump_height

    def fall_budget(self) -> int:
        phase_cap = self.phase.max_fall_tiles
        if phase_cap is not None and phase_cap > 0:
            return min(self.max_fall_height, int(phase_cap))
        return self.max_fall_height

    def generate_sketch_dict(
        self, name: str, difficulty: float = 0.5
    ) -> dict[str, Any]:
        """Return a dense sketch dict ready for ``parse_level_sketch`` / import.

        ``difficulty`` is retained for call-site compatibility; phase constraints
        dominate structure choice when provided.
        """
        _ = _clamp(float(difficulty), 0.0, 1.0)
        grid = SketchGrid()
        clearance = ClearanceHeightState.from_config(
            delver_height=self.delver_height,
            cfg=self.cfg,
            rng=self.rng,
        )
        spawn_w = int(self.cfg.SPAWN_PLATFORM_WIDTH)
        spawn_clearance = clearance.current
        start = paint_floor_run(
            grid,
            x0=0,
            x1=spawn_w,
            floor_y=0,
            clearance_h=spawn_clearance,
        )
        if start is None:
            raise ValueError("Failed to paint spawn platform.")

        head = PathHead(
            direction=1,
            segment=start,
            prev_floor_y=None,
            clearance_h=spawn_clearance,
        )
        start_seg = start
        path_segments: list[FloorSeg] = [start]

        min_steps = int(
            self.phase.min_path_steps
            if self.phase.min_path_steps is not None
            else self.cfg.MIN_PATH_STEPS
        )
        max_steps = int(
            self.phase.max_path_steps
            if self.phase.max_path_steps is not None
            else self.cfg.MAX_PATH_STEPS
        )
        max_steps = max(min_steps, max_steps)
        target_steps = self.rng.randint(min_steps, max_steps)

        stuck = 0
        steps = 0
        # Goal sits on the farthest frontier from spawn (not a backtracked tip).
        goal_seg = start
        best_dist = _segment_dist(start, start)

        while steps < target_steps and stuck < 48:
            placed = self._step(grid, head, path_segments, clearance)
            if placed is None:
                stuck += 1
                continue
            head = placed
            path_segments.append(head.segment)
            dist = _segment_dist(start_seg, head.segment)
            if dist >= best_dist:
                best_dist = dist
                goal_seg = head.segment
            steps += 1
            stuck = 0

        if len(path_segments) < 2:
            # Guaranteed hop so sketches stay valid (respect min gap when possible).
            min_gap = int(self.cfg.MIN_GAP_TILES)
            max_gap = self.max_gap_for_delta(0)
            gap = min_gap if max_gap >= min_gap else max(1, max_gap)
            next_h = clearance.sample_next(self.rng)
            forced = try_pit(
                grid,
                head,
                gap=gap,
                delta_h=0,
                landing_width=int(self.cfg.MIN_PLATFORM_WIDTH),
                clearance_h=next_h,
                span_clearance_h=self._span_height_for(next_h),
                span_edge_overlap=int(self.cfg.get("span_edge_overlap_tiles", 1)),
            )
            if forced is not None:
                head = forced
                path_segments.append(head.segment)
                goal_seg = head.segment

        return finalize_sketch_dict(
            grid,
            name=name,
            start_seg=start_seg,
            end_seg=goal_seg,
            pad_tiles=int(self.cfg.FINALIZE_PAD_TILES),
            top_margin_tiles=int(self.cfg.TOP_MARGIN_TILES),
        )

    def generate_sketch(self, name: str, difficulty: float = 0.5) -> LevelSketch:
        return parse_level_sketch(self.generate_sketch_dict(name, difficulty))

    def _span_height_for(self, *floor_heights: int) -> int:
        """Jump vault above takeoff: at least JH+DH, and at least ambient floor height."""
        ambient = max(floor_heights) if floor_heights else self.floor_clearance_h
        return max(self.span_clearance_h, ambient)

    def _span_edge_overlap(self) -> int:
        return max(2, int(self.cfg.get("span_edge_overlap_tiles", 2)))

    def _sample_shift_transition_gap(self) -> int:
        lo = int(self.cfg.get("min_shift_transition_gap_tiles", 2))
        hi = int(self.cfg.get("max_shift_transition_gap_tiles", max(lo, 4)))
        return self.rng.randint(lo, max(lo, hi))

    def _step(
        self,
        grid: SketchGrid,
        head: PathHead,
        path_segments: list[FloorSeg],
        clearance: ClearanceHeightState,
    ) -> PathHead | None:
        _ = path_segments
        weights = self._structure_weights(head)
        active = {k: w for k, w in weights.items() if w > 0}
        for _ in range(16):
            if not active:
                return None
            keys = list(active.keys())
            probs = [active[k] for k in keys]
            for i, k in enumerate(keys):
                if k == "continue":
                    probs[i] *= float(self.cfg.FORWARD_BIAS)
            pick = self.rng.choices(keys, weights=probs, k=1)[0]
            result = self._apply_structure(grid, head, pick, clearance)
            if result is not None:
                # Continuity tracks ambient floor clearance only (already sampled).
                if pick == "pit" and self.rng.random() < float(
                    self.cfg.NEIGHBOR_PIT_BRIDGE_ODDS
                ):
                    bridged = self._try_neighbor_pit_bridge(grid, result, clearance)
                    if bridged is not None:
                        return bridged
                if pick in ("continue", "shift") and self.rng.random() < float(
                    self.cfg.DELAY_LEDGE_ODDS
                ):
                    ledged = self._try_delay_ledge(grid, result, clearance)
                    if ledged is not None:
                        return ledged
                if (
                    pick in ("pit", "shift", "switchback")
                    and can_turn(result)
                    and float(self.cfg.POST_CLIMB_TURN_ODDS) > 0.0
                ):
                    if self.rng.random() < float(self.cfg.POST_CLIMB_TURN_ODDS):
                        turned = try_turn(result)
                        if turned is not None:
                            next_h = clearance.sample_next(self.rng)
                            extended = try_continue(
                                grid,
                                turned,
                                length=self._sample_continue_length(),
                                clearance_h=next_h,
                            )
                            if extended is not None:
                                return extended
                            return turned
                return result
            active[pick] *= 0.25
            if active[pick] < 0.05:
                del active[pick]
        return None

    def _apply_structure(
        self,
        grid: SketchGrid,
        head: PathHead,
        kind: str,
        clearance: ClearanceHeightState,
    ) -> PathHead | None:
        next_h = clearance.sample_next(self.rng)
        span_h = self._span_height_for(next_h)
        overlap = self._span_edge_overlap()

        if kind == "continue":
            return try_continue(
                grid,
                head,
                length=self._sample_continue_length(),
                clearance_h=next_h,
            )
        if kind == "pit":
            if not self.phase.allow_pits:
                return None
            delta_h = self._sample_delta_h()
            gap = self._sample_gap(delta_h)
            if gap is None:
                return None
            return try_pit(
                grid,
                head,
                gap=gap,
                delta_h=delta_h,
                landing_width=self._sample_width(),
                clearance_h=next_h,
                span_clearance_h=span_h,
                span_edge_overlap=overlap,
            )
        if kind == "shift":
            if not self.phase.allow_floor_height_shifts:
                return None
            delta_h = self._sample_delta_h()
            if delta_h == 0:
                for _ in range(6):
                    delta_h = self._sample_delta_h()
                    if delta_h != 0:
                        break
                if delta_h == 0:
                    return None
            return try_floor_height_shift(
                grid,
                head,
                delta_h=delta_h,
                length=self._sample_width(),
                clearance_h=next_h,
                span_clearance_h=span_h,
                span_edge_overlap=self._sample_shift_transition_gap(),
            )
        if kind == "turn":
            turned = try_turn(head)
            if turned is None:
                return None
            extended = try_continue(
                grid,
                turned,
                length=self._sample_continue_length(),
                clearance_h=next_h,
            )
            if extended is not None:
                return extended
            gap = self._sample_gap(0)
            if gap is None:
                return turned
            pitted = try_pit(
                grid,
                turned,
                gap=gap,
                delta_h=0,
                landing_width=self._sample_width(),
                clearance_h=next_h,
                span_clearance_h=span_h,
                span_edge_overlap=overlap,
            )
            return pitted if pitted is not None else turned
        if kind == "switchback":
            if self.rise_budget() < 1:
                return None
            if not self.phase.allow_pits and not self.phase.allow_floor_height_shifts:
                return None
            climb = max(1, self.rng.randint(1, max(1, self.rise_budget())))
            return try_switchback(
                grid,
                head,
                climb_delta=climb,
                length=self._sample_width(),
                continue_length=self._sample_continue_length(),
                clearance_h=next_h,
                span_clearance_h=span_h,
                span_edge_overlap=overlap,
            )
        return None

    def _structure_weights(self, head: PathHead) -> dict[str, float]:
        cont = (
            self.phase.continue_weight
            if self.phase.continue_weight is not None
            else float(self.cfg.CONTINUE_WEIGHT)
        )
        pit = (
            self.phase.pit_weight
            if self.phase.pit_weight is not None
            else float(self.cfg.PIT_WEIGHT)
        )
        shift = (
            self.phase.floor_height_shift_weight
            if self.phase.floor_height_shift_weight is not None
            else float(self.cfg.FLOOR_HEIGHT_SHIFT_WEIGHT)
        )
        if not self.phase.allow_pits:
            pit = 0.0
        if not self.phase.allow_floor_height_shifts:
            shift = 0.0

        turn = float(self.cfg.TURN_WEIGHT)
        if not can_turn(head):
            turn = 0.0
        elif head.prev_floor_y is not None and head.floor_y < head.prev_floor_y:
            turn *= float(self.cfg.POST_CLIMB_TURN_BOOST)

        switchback = float(self.cfg.SWITCHBACK_WEIGHT)
        if self.rise_budget() < 1:
            switchback = 0.0
        if not self.phase.allow_pits and not self.phase.allow_floor_height_shifts:
            switchback = 0.0

        return {
            "continue": cont,
            "pit": pit,
            "shift": shift,
            "turn": turn,
            "switchback": switchback,
        }

    def _sample_delta_h(self) -> int:
        if self.phase.force_delta_h is not None:
            return int(self.phase.force_delta_h)

        rise = self.rise_budget()
        fall = self.fall_budget()
        lo = -fall
        hi = rise
        if self.phase.prefer_positive_delta:
            lo = max(lo, 0)
        if self.phase.prefer_negative_delta:
            hi = min(hi, 0)
        if lo > hi:
            return 0

        min_mag = int(self.cfg.MIN_DELTA_MAGNITUDE)
        candidates = [d for d in range(lo, hi + 1) if abs(d) >= min_mag or d == 0]
        if self.phase.prefer_positive_delta:
            candidates = [d for d in candidates if d > 0] or candidates
        if self.phase.prefer_negative_delta:
            candidates = [d for d in candidates if d < 0] or candidates
        if not candidates:
            return 0
        return self.rng.choice(candidates)

    def _sample_gap(self, delta_h: int) -> int | None:
        max_gap = self.max_gap_for_delta(delta_h)
        min_gap = int(self.cfg.MIN_GAP_TILES)
        if max_gap < min_gap:
            return None
        return self.rng.randint(min_gap, max_gap)

    def _sample_width(self) -> int:
        lo = int(self.cfg.MIN_PLATFORM_WIDTH)
        hi = int(self.cfg.MAX_PLATFORM_WIDTH)
        return self.rng.randint(lo, max(lo, hi))

    def _sample_continue_length(self) -> int:
        lo = int(self.cfg.MIN_CONTINUE_LENGTH)
        hi = int(self.cfg.MAX_CONTINUE_LENGTH)
        return self.rng.randint(lo, max(lo, hi))

    def _try_neighbor_pit_bridge(
        self,
        grid: SketchGrid,
        head: PathHead,
        clearance: ClearanceHeightState,
    ) -> PathHead | None:
        """Optional: short bridge then a second pit."""
        bridge_w = int(self.cfg.NEIGHBOR_PIT_BRIDGE_WIDTH)
        bridge_h = clearance.sample_next(self.rng)
        bridged = try_continue(
            grid, head, length=bridge_w, clearance_h=bridge_h
        )
        if bridged is None:
            return None
        delta_h = self._sample_delta_h()
        gap = self._sample_gap(delta_h)
        if gap is None:
            return bridged
        next_h = clearance.sample_next(self.rng)
        second = try_pit(
            grid,
            bridged,
            gap=gap,
            delta_h=delta_h,
            landing_width=self._sample_width(),
            clearance_h=next_h,
            span_clearance_h=self._span_height_for(next_h),
            span_edge_overlap=self._span_edge_overlap(),
        )
        return second if second is not None else bridged

    def _try_delay_ledge(
        self,
        grid: SketchGrid,
        head: PathHead,
        clearance: ClearanceHeightState,
    ) -> PathHead | None:
        """Optional short ledge at ~¾ jump height (delay platform)."""
        frac = float(self.cfg.DELAY_LEDGE_JUMP_HEIGHT_FRACTION)
        rise = max(1, int(math.floor(self.jump_height * frac)))
        next_h = clearance.sample_next(self.rng)
        return try_floor_height_shift(
            grid,
            head,
            delta_h=rise,
            length=int(self.cfg.DELAY_LEDGE_WIDTH),
            clearance_h=next_h,
            span_clearance_h=self._span_height_for(next_h),
            span_edge_overlap=self._span_edge_overlap(),
        )


def _segment_dist(origin: FloorSeg, seg: FloorSeg) -> int:
    """Chebyshev-ish distance of segment center from origin (path frontier metric)."""
    ox = (origin.x0 + origin.x1) // 2
    sx = (seg.x0 + seg.x1) // 2
    return abs(sx - ox) + abs(seg.y - origin.y)


# --- Back-compat helpers used by older tests / imports ------------------------


@dataclass(frozen=True)
class PlatformSeg:
    """Legacy segment type (inclusive-exclusive x, floor row y)."""

    x0: int
    x1: int
    y: int

    @property
    def width(self) -> int:
        return self.x1 - self.x0


class PathShape:
    """Legacy enum stub — shapes are no longer used by the clearance generator."""

    LINEAR = "linear"
    STAIRS = "stairs"
    ZIGZAG = "zigzag"
    SWITCHBACK = "switchback"


def path_has_direction_change(segments: list[PlatformSeg] | list[FloorSeg]) -> bool:
    if len(segments) < 3:
        return False
    signs: list[int] = []
    for a, b in zip(segments, segments[1:]):
        if b.x0 >= a.x1:
            signs.append(1)
        elif a.x0 >= b.x1:
            signs.append(-1)
    for s0, s1 in zip(signs, signs[1:]):
        if s0 != s1:
            return True
    return False


def max_horizontal_gap(segments: list[PlatformSeg] | list[FloorSeg]) -> int:
    best = 0
    for a, b in zip(segments, segments[1:]):
        if b.x0 >= a.x1:
            best = max(best, b.x0 - a.x1)
        elif a.x0 >= b.x1:
            best = max(best, a.x0 - b.x1)
    return best
