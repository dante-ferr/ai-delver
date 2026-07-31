"""CLI: generate a procedural platforming pack under level_saves/generated/."""

from __future__ import annotations

import json
import sys

from level.config import procedural_config
from level.procedural.pack import generate_platforming_pack
from utils.level_groups import (
    LevelGroupError,
    load_level_groups,
    normalize_group_name,
    save_level_groups,
)


def print_json(event: str, **kwargs):
    print(json.dumps({"event": event, **kwargs}), flush=True)


def run_gen_platforming_pack(args):
    """Generate levels, save under generated/<group>/, register @group."""
    try:
        group = normalize_group_name(str(args.group))
    except LevelGroupError as exc:
        print_json("error", message=str(exc))
        sys.exit(1)

    proc = procedural_config
    if bool(getattr(args, "no_curriculum", False)):
        use_curriculum = False
    else:
        # None → pack reads procedural_platforming.use_curriculum
        use_curriculum = None
    count = getattr(args, "count", None)
    if count is not None:
        count = int(count)
        if count < 1:
            print_json("error", message="--count must be >= 1")
            sys.exit(1)

    seed = getattr(args, "seed", None)

    def _register(group_name: str, level_names: list[str]) -> None:
        groups = load_level_groups()
        groups[group_name] = level_names
        save_level_groups(groups)

    try:
        result = generate_platforming_pack(
            group,
            count=count,
            seed=seed,
            curriculum=use_curriculum,
            replace=True,
            register_group=_register,
        )
    except Exception as exc:
        print_json("error", message=f"Failed to generate pack: {exc}")
        sys.exit(1)

    print_json(
        "platforming_pack_generated",
        group=result.group,
        count=len(result.level_names),
        levels=result.level_names,
        phases=result.phase_names,
        curriculum=result.curriculum,
        path=str(result.path),
        seed=result.seed,
        message=(
            f"Generated {len(result.level_names)} levels in group '@{result.group}'"
            + (" (curriculum phases)." if result.curriculum else ".")
        ),
    )
