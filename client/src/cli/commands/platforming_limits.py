import json
import sys
from pathlib import Path

from level.sketch.platforming_limits import (
    PlatformingLimitsError,
    compute_platforming_limits,
    delver_height_tiles,
    jump_height_tiles,
    limits_to_jsonable,
    max_gap_tiles_for_delta_height,
)


def print_json(event: str, **kwargs):
    print(json.dumps({"event": event, **kwargs}), flush=True)


def run_platforming_limits(args):
    """Compute jump/gap authoring limits from runtime physics TOML configs."""
    try:
        delver = Path(args.delver_toml) if args.delver_toml else None
        world = Path(args.world_toml) if args.world_toml else None
        limits = compute_platforming_limits(delver_toml=delver, world_toml=world)
        payload = limits_to_jsonable(limits)

        # Always surface explicit jump / Delver height for authoring scripts.
        payload["jump_height_tiles"] = jump_height_tiles(
            delver_toml=delver, world_toml=world
        )
        payload["delver_height_tiles"] = delver_height_tiles(delver_toml=delver)

        delta_height = getattr(args, "delta_height", None)
        if delta_height is not None:
            gap = max_gap_tiles_for_delta_height(
                int(delta_height),
                delver_toml=delver,
                world_toml=world,
            )
            payload["delta_height"] = int(delta_height)
            payload["max_gap_tiles_for_delta_height"] = gap
            print_json(
                "platforming_limits",
                message=(
                    f"Max gap for delta_height={int(delta_height)} is {gap} tiles. "
                    "Positive delta_height = climb."
                ),
                **payload,
            )
            return

        print_json(
            "platforming_limits",
            message=(
                "Computed platforming limits from physics configs. "
                "Use recommended_*_tiles when authoring level sketches. "
                "Pass --delta-height N for gap-vs-height lookups."
            ),
            **payload,
        )
    except PlatformingLimitsError as exc:
        print_json("error", message=str(exc))
        sys.exit(1)
    except Exception as exc:
        print_json("error", message=f"Failed to compute platforming limits: {exc}")
        sys.exit(1)
