"""Derive platforming spacing limits from runtime physics TOML configs."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore

from level.config import config as level_config
from level.exceptions import LevelError
from level.world_object_sizes import delver_size_tiles


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
    ray_offset_inward_px: float

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

    # Footprint helpers
    delver_height_tiles: int
    delver_width_tiles: int

    source_delver_toml: str
    source_world_toml: str


def default_delver_toml() -> Path:
    return (
        level_config.PROJECT_ROOT
        / "runtime"
        / "src"
        / "world_objects"
        / "delver"
        / "delver.toml"
    )


def default_world_toml() -> Path:
    return level_config.PROJECT_ROOT / "runtime" / "src" / "engine" / "world.toml"


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
    while falling, then jump, hold run, land at the takeoff height. Ground rays are inset
    by ``ray_offset_inward``, so effective overhang is ``player_width - 2·ray_offset_inward``
    (not the full collider width).
    """
    params = _physics_params(delver_toml, world_toml, tile_width_px, tile_height_px)
    tile_w = params["tile_w"]
    tile_h = params["tile_h"]
    delver_path = params["delver_path"]
    world_path = params["world_path"]

    steady_run = params["steady_run"]
    dt = params["dt"]
    jump_impulse = params["jump_impulse"]
    gravity = params["gravity"]
    abs_g = abs(gravity)
    jump_tolerance = params["jump_tolerance"]
    player_width = params["player_width"]
    player_height = params["player_height"]
    ray_offset_inward = params["ray_offset_inward"]

    # Ballistic height — matches Rapier empirical apex (~70px / 4.4 tiles).
    max_jump_height_px = (jump_impulse * jump_impulse) / (2.0 * abs_g)
    jump_air_time_s = (2.0 * jump_impulse) / abs_g
    max_jump_height_tiles = max_jump_height_px / tile_h

    sim_gap_px = _simulate_coyote_gap_reach(
        steady_run_speed=steady_run,
        jump_impulse=jump_impulse,
        gravity=gravity,
        jump_tolerance_s=jump_tolerance,
        dt=dt,
        landing_y_px=0.0,
    )
    # Ground rays sit inward from each collider edge, so last grounded / first landing
    # contact uses overhang of (half_w - ray_offset) per ledge.
    overhang_px = player_width - 2.0 * ray_offset_inward
    sim_gap_px_effective = sim_gap_px + overhang_px
    sim_gap_tiles = sim_gap_px_effective / tile_w

    # Whole-tile budgets.
    # Rise: surface-to-surface row delta. floor(4.375 → 4). Apex (~70px) sits above +4 (64px).
    # Stack: when counting solid cells in a column *including the floor*, max is rise+1.
    # Gap: floor coyote COM travel + ray-inset overhang (round would overclaim unreachable gaps).
    recommended_max_rise = max(1, math.floor(max_jump_height_tiles + 1e-6))
    recommended_max_stack = recommended_max_rise + 1
    recommended_max_gap = max(1, math.floor((sim_gap_tiles - 0.5) + 1e-6))
    player_height_tiles = player_height / tile_h
    recommended_ceiling = max(
        1, math.ceil(player_height_tiles + max_jump_height_tiles * 0.5)
    )

    delver_w, delver_h = delver_size_tiles(
        str(delver_path),
        tile_width=int(tile_w),
        tile_height=int(tile_h),
    )

    return PlatformingLimits(
        tile_width_px=tile_w,
        tile_height_px=tile_h,
        gravity_px_s2=gravity,
        jump_impulse_px_s=jump_impulse,
        move_force=params["move_force"],
        linear_damping=params["linear_damping"],
        max_vx_px_s=params["max_vx"],
        player_width_px=player_width,
        player_height_px=player_height,
        physics_fps=params["physics_fps"],
        jump_tolerance_s=jump_tolerance,
        ray_offset_inward_px=ray_offset_inward,
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
        delver_height_tiles=delver_h,
        delver_width_tiles=delver_w,
        source_delver_toml=str(delver_path),
        source_world_toml=str(world_path),
    )


def jump_height_tiles(
    delver_toml: Path | None = None,
    world_toml: Path | None = None,
    tile_height_px: float | None = None,
) -> int:
    """Floored max reliable surface rise in tiles (authoring jump height)."""
    return compute_platforming_limits(
        delver_toml=delver_toml,
        world_toml=world_toml,
        tile_height_px=tile_height_px,
    ).recommended_max_rise_tiles


def delver_height_tiles(
    delver_toml: Path | None = None,
    tile_width_px: float | None = None,
    tile_height_px: float | None = None,
) -> int:
    """Delver footprint height in tiles."""
    path = Path(delver_toml) if delver_toml else default_delver_toml()
    tile_w = int(
        tile_width_px if tile_width_px is not None else level_config.TILE_WIDTH
    )
    tile_h = int(
        tile_height_px if tile_height_px is not None else level_config.TILE_HEIGHT
    )
    return delver_size_tiles(str(path), tile_width=tile_w, tile_height=tile_h)[1]


def max_gap_tiles(
    delver_toml: Path | None = None,
    world_toml: Path | None = None,
) -> int:
    """Same-height recommended max gap in tiles."""
    return compute_platforming_limits(
        delver_toml=delver_toml, world_toml=world_toml
    ).recommended_max_gap_tiles


def max_gap_tiles_for_delta_height(
    delta_h: int,
    *,
    delver_toml: Path | None = None,
    world_toml: Path | None = None,
    tile_width_px: float | None = None,
    tile_height_px: float | None = None,
) -> int:
    """Max empty horizontal gap (tiles) for a surface height change of ``delta_h``.

    ``delta_h`` = landing surface − takeoff surface in tiles (**positive = climb**).
    Results are cached per physics fingerprint + delta.
    """
    params = _physics_params(delver_toml, world_toml, tile_width_px, tile_height_px)
    fingerprint = (
        round(params["tile_w"], 6),
        round(params["tile_h"], 6),
        round(params["gravity"], 6),
        round(params["jump_impulse"], 6),
        round(params["steady_run"], 6),
        round(params["jump_tolerance"], 6),
        round(params["dt"], 9),
        round(params["player_width"], 6),
        round(params["ray_offset_inward"], 6),
        int(delta_h),
    )
    return _cached_max_gap_tiles_for_delta(fingerprint)


@lru_cache(maxsize=256)
def _cached_max_gap_tiles_for_delta(fingerprint: tuple[Any, ...]) -> int:
    (
        tile_w,
        tile_h,
        gravity,
        jump_impulse,
        steady_run,
        jump_tolerance,
        dt,
        player_width,
        ray_offset_inward,
        delta_h,
    ) = fingerprint
    landing_y_px = float(delta_h) * float(tile_h)

    sim_gap_px = _simulate_coyote_gap_reach(
        steady_run_speed=float(steady_run),
        jump_impulse=float(jump_impulse),
        gravity=float(gravity),
        jump_tolerance_s=float(jump_tolerance),
        dt=float(dt),
        landing_y_px=landing_y_px,
    )
    if sim_gap_px <= 0.0:
        return 0

    overhang_px = float(player_width) - 2.0 * float(ray_offset_inward)
    sim_gap_px_effective = sim_gap_px + overhang_px
    sim_gap_tiles = sim_gap_px_effective / float(tile_w)
    return max(0, math.floor((sim_gap_tiles - 0.5) + 1e-6))


def _physics_params(
    delver_toml: Path | None,
    world_toml: Path | None,
    tile_width_px: float | None,
    tile_height_px: float | None,
) -> dict[str, Any]:
    delver_path = Path(delver_toml) if delver_toml else default_delver_toml()
    world_path = Path(world_toml) if world_toml else default_world_toml()
    delver = _load_toml(delver_path)
    world = _load_toml(world_path)

    tile_w = float(
        tile_width_px if tile_width_px is not None else level_config.TILE_WIDTH
    )
    tile_h = float(
        tile_height_px if tile_height_px is not None else level_config.TILE_HEIGHT
    )
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
    ray_offset_inward = float(delver["ray_offset_inward"])

    if jump_impulse <= 0:
        raise PlatformingLimitsError("jump_impulse must be positive.")
    if linear_damping <= 0:
        raise PlatformingLimitsError("linear_damping must be positive.")
    if physics_fps <= 0:
        raise PlatformingLimitsError("physics_fps must be positive.")

    steady_run = min(move_force / linear_damping, max_vx)
    dt = 1.0 / physics_fps

    return {
        "delver_path": delver_path,
        "world_path": world_path,
        "tile_w": tile_w,
        "tile_h": tile_h,
        "gravity": gravity,
        "jump_impulse": jump_impulse,
        "move_force": move_force,
        "linear_damping": linear_damping,
        "max_vx": max_vx,
        "physics_fps": physics_fps,
        "jump_tolerance": jump_tolerance,
        "player_width": player_width,
        "player_height": player_height,
        "ray_offset_inward": ray_offset_inward,
        "steady_run": steady_run,
        "dt": dt,
    }


def _simulate_coyote_gap_reach(
    *,
    steady_run_speed: float,
    jump_impulse: float,
    gravity: float,
    jump_tolerance_s: float,
    dt: float,
    landing_y_px: float = 0.0,
) -> float:
    """Horizontal COM travel for: run off ledge → coyote window → jump → land.

    Physics y increases upward. ``landing_y_px`` is the landing surface relative to
    takeoff (positive = climb). Uses semi-implicit Euler matching Rapier.
    Returns 0 if the landing height is unreachable within the timeout.
    """
    vx = steady_run_speed
    x = 0.0
    y = 0.0
    vy = 0.0
    t = 0.0
    max_y = 0.0

    # Fall while coyote allows a late jump (still holding run).
    while t < jump_tolerance_s - 1e-9:
        vy += gravity * dt
        x += vx * dt
        y += vy * dt
        t += dt
        max_y = max(max_y, y)

    # Coyote jump: set upward velocity like LocomotionMotor::try_jump.
    vy = jump_impulse

    while True:
        vy += gravity * dt
        x += vx * dt
        y += vy * dt
        t += dt
        max_y = max(max_y, y)
        # Land only after reaching at least the landing height, then falling onto it.
        if vy <= 0.0 and y <= landing_y_px and max_y >= landing_y_px - 1e-6:
            return x
        if t > 5.0:
            return 0.0


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
