"""Derive platforming spacing limits from runtime physics TOML configs."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore

from level.config import PROJECT_ROOT, TILE_HEIGHT, TILE_WIDTH
from level.exceptions import LevelError


class PlatformingLimitsError(LevelError):
    """Raised when physics configs cannot be read or are invalid."""


@dataclass(frozen=True)
class PlatformingLimits:
    """Computed locomotion envelope for authoring / validating sketches."""

    tile_width_px: float
    tile_height_px: float
    gravity_px_s2: float
    jump_impulse_px_s: float
    move_force: float
    linear_damping: float
    max_vx_px_s: float
    player_width_px: float
    player_height_px: float
    physics_fps: float
    jump_tolerance_s: float

    # Derived (analytic / continuous)
    steady_run_speed_px_s: float
    max_jump_height_px: float
    max_jump_height_tiles: float
    jump_air_time_s: float

    # Derived (Rapier-validated ballistic height + discrete coyote gap sim)
    simulated_max_jump_height_px: float
    simulated_max_jump_height_tiles: float
    simulated_same_height_air_time_s: float
    simulated_coyote_gap_reach_px: float
    simulated_coyote_gap_reach_tiles: float

    # Authoring budgets in whole tiles (use these when placing sketch platforms)
    recommended_max_rise_tiles: int
    # Visual pillar height when the floor cell is part of the stack (rise + 1).
    # Example: a 4-tile-tall column including the floor has a +3 surface rise.
    recommended_max_stack_tiles_including_floor: int
    recommended_max_gap_tiles: int
    recommended_min_ceiling_clearance_tiles: int

    source_delver_toml: str
    source_world_toml: str


def default_delver_toml() -> Path:
    return PROJECT_ROOT / "runtime" / "src" / "world_objects" / "delver" / "delver.toml"


def default_world_toml() -> Path:
    return PROJECT_ROOT / "runtime" / "src" / "engine" / "world.toml"


def compute_platforming_limits(
    delver_toml: Path | None = None,
    world_toml: Path | None = None,
    tile_width_px: float | None = None,
    tile_height_px: float | None = None,
) -> PlatformingLimits:
    """Load physics TOMLs and compute jump / gap limits in pixels and tiles.

    Horizontal motion (``LocomotionMotor::calculate_horizontal_velocity``), steady run:

        move_force - linear_damping * vx = 0
        => vx_ss = min(move_force / linear_damping, max_vx)

    Vertical: continuous ballistic ``h = jump_impulse² / (2|g|)``. Empirically Rapier
    matches this within ~1px (validated by ``measures_jump_apex_and_ledge_landing``);
    a naive ``y += v·dt; v += g·dt`` discrete loop *overestimates* height and must not
    be used for rise budgets.

    Max gap uses a **coyote edge jump**: run off a ledge for up to ``jump_tolerance_max``
    while falling, then jump, hold run, land at the takeoff height. Effective reach also
    adds ``player_width`` so toe-overhang on both ledges is counted (matches how gaps
    feel in-editor).
    """
    delver_path = Path(delver_toml) if delver_toml else default_delver_toml()
    world_path = Path(world_toml) if world_toml else default_world_toml()
    delver = _load_toml(delver_path)
    world = _load_toml(world_path)

    tile_w = float(tile_width_px if tile_width_px is not None else TILE_WIDTH)
    tile_h = float(tile_height_px if tile_height_px is not None else TILE_HEIGHT)
    if tile_w <= 0 or tile_h <= 0:
        raise PlatformingLimitsError("Tile size must be positive.")

    gravity = float(world["gravity"])
    abs_g = abs(gravity)
    if abs_g <= 0:
        raise PlatformingLimitsError("World gravity magnitude must be positive.")

    jump_impulse = float(delver["jump_impulse"])
    move_force = float(delver["move_force"])
    linear_damping = float(delver["linear_damping"])
    max_vx = float(delver["max_vx"])
    physics_fps = float(world["physics_fps"])
    jump_tolerance = float(delver["jump_tolerance_max"])
    player_width = float(delver["player_width"])
    player_height = float(delver["player_height"])

    if jump_impulse <= 0:
        raise PlatformingLimitsError("jump_impulse must be positive.")
    if linear_damping <= 0:
        raise PlatformingLimitsError("linear_damping must be positive.")
    if physics_fps <= 0:
        raise PlatformingLimitsError("physics_fps must be positive.")

    steady_run = min(move_force / linear_damping, max_vx)
    dt = 1.0 / physics_fps

    # Ballistic height — matches Rapier empirical apex (~48px / 3 tiles).
    max_jump_height_px = (jump_impulse * jump_impulse) / (2.0 * abs_g)
    jump_air_time_s = (2.0 * jump_impulse) / abs_g
    max_jump_height_tiles = max_jump_height_px / tile_h

    sim_gap_px = _simulate_coyote_gap_reach(
        steady_run_speed=steady_run,
        jump_impulse=jump_impulse,
        gravity=gravity,
        jump_tolerance_s=jump_tolerance,
        dt=dt,
    )
    # Toe overhang on takeoff + landing ledges.
    sim_gap_px_effective = sim_gap_px + player_width
    sim_gap_tiles = sim_gap_px_effective / tile_w

    # Whole-tile budgets.
    # Rise: surface-to-surface row delta. floor(4.375 → 4). Apex (~70px) sits above +4 (64px).
    # Stack: when counting solid cells in a column *including the floor*, max is rise+1.
    # Gap: round coyote + toe-overhang reach so in-editor feel matches.
    recommended_max_rise = max(1, math.floor(max_jump_height_tiles + 1e-6))
    recommended_max_stack = recommended_max_rise + 1
    recommended_max_gap = max(1, int(round(sim_gap_tiles)))
    player_height_tiles = player_height / tile_h
    recommended_ceiling = max(
        1, math.ceil(player_height_tiles + max_jump_height_tiles * 0.5)
    )

    return PlatformingLimits(
        tile_width_px=tile_w,
        tile_height_px=tile_h,
        gravity_px_s2=gravity,
        jump_impulse_px_s=jump_impulse,
        move_force=move_force,
        linear_damping=linear_damping,
        max_vx_px_s=max_vx,
        player_width_px=player_width,
        player_height_px=player_height,
        physics_fps=physics_fps,
        jump_tolerance_s=jump_tolerance,
        steady_run_speed_px_s=steady_run,
        max_jump_height_px=max_jump_height_px,
        max_jump_height_tiles=max_jump_height_tiles,
        jump_air_time_s=jump_air_time_s,
        simulated_max_jump_height_px=max_jump_height_px,
        simulated_max_jump_height_tiles=max_jump_height_tiles,
        simulated_same_height_air_time_s=jump_air_time_s,
        simulated_coyote_gap_reach_px=sim_gap_px_effective,
        simulated_coyote_gap_reach_tiles=sim_gap_tiles,
        recommended_max_rise_tiles=recommended_max_rise,
        recommended_max_stack_tiles_including_floor=recommended_max_stack,
        recommended_max_gap_tiles=recommended_max_gap,
        recommended_min_ceiling_clearance_tiles=recommended_ceiling,
        source_delver_toml=str(delver_path),
        source_world_toml=str(world_path),
    )


def _simulate_coyote_gap_reach(
    *,
    steady_run_speed: float,
    jump_impulse: float,
    gravity: float,
    jump_tolerance_s: float,
    dt: float,
) -> float:
    """Horizontal travel for: run off ledge → coyote window → jump → land at y<=0."""
    vx = steady_run_speed
    x = 0.0
    y = 0.0
    vy = 0.0
    t = 0.0

    # Fall while coyote allows a late jump (still holding run).
    while t < jump_tolerance_s - 1e-9:
        x += vx * dt
        y += vy * dt
        vy += gravity * dt
        t += dt

    # Coyote jump: set upward velocity like LocomotionMotor::try_jump.
    vy = jump_impulse

    while True:
        x += vx * dt
        y += vy * dt
        vy += gravity * dt
        t += dt
        if y <= 0.0 and vy <= 0.0:
            break
        if t > 5.0:
            break
    return x


def limits_to_jsonable(limits: PlatformingLimits) -> dict[str, Any]:
    """Serialize limits for CLI JSON stdout (round floats for readability)."""
    raw = asdict(limits)
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if isinstance(value, float):
            out[key] = round(value, 6)
        else:
            out[key] = value
    return out


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PlatformingLimitsError(f"Failed to read physics config '{path}': {exc}") from exc
    try:
        data = tomllib.loads(text)
    except Exception as exc:
        raise PlatformingLimitsError(f"Invalid TOML in '{path}': {exc}") from exc
    if not isinstance(data, dict):
        raise PlatformingLimitsError(f"Physics config '{path}' must be a TOML table.")
    return data
