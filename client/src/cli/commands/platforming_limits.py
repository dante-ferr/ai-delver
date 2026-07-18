import json
import sys
from pathlib import Path

from level.sketch.platforming_limits import (
    PlatformingLimitsError,
    compute_platforming_limits,
    limits_to_jsonable,
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
        print_json(
            "platforming_limits",
            message=(
                "Computed platforming limits from physics configs. "
                "Use recommended_*_tiles when authoring level sketches."
            ),
            **payload,
        )
    except PlatformingLimitsError as exc:
        print_json("error", message=str(exc))
        sys.exit(1)
    except Exception as exc:
        print_json("error", message=f"Failed to compute platforming limits: {exc}")
        sys.exit(1)
