"""Generate / replace a procedural platforming pack on disk."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from level import LevelSketchError, LevelSketchImporter
from level.config import procedural_config, reload_configs
from level.procedural.curriculum import iter_curriculum_slots
from level.procedural.platforming_generator import (
    PhaseConstraints,
    ProceduralPlatformingGenerator,
)
from level.resolve_level import generated_levels_dir
from level.sketch.platforming_limits import compute_platforming_limits


@dataclass(frozen=True)
class PackResult:
    group: str
    level_names: list[str]
    phase_names: list[str]
    path: Path
    seed: int | None
    curriculum: bool


def generate_platforming_pack(
    group: str,
    *,
    count: int | None = None,
    seed: int | None = None,
    curriculum: bool | None = None,
    replace: bool = False,
    register_group: Any | None = None,
) -> PackResult:
    """Build levels under ``generated/<group>/``.

    ``register_group`` is an optional callback ``(group, level_names) -> None``
    used by the client to update ``level_groups.json`` without importing it here.
    """
    # Pick up TOML edits without restarting the playtest / CLI process.
    reload_configs()
    proc = procedural_config

    if count is not None and count < 1:
        raise ValueError("count must be >= 1")

    if curriculum is None:
        curriculum = bool(proc.get("use_curriculum", True))

    out_root = generated_levels_dir() / group
    if out_root.exists():
        if not replace:
            raise FileExistsError(
                f"Pack directory already exists: {out_root}. Pass replace=True."
            )
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    if seed is None:
        seed = int(proc.get("seed", 0))

    limits = compute_platforming_limits()
    importer = LevelSketchImporter()

    if curriculum:
        slots = list(iter_curriculum_slots(count=count, cfg=proc))
    else:
        n = int(count if count is not None else proc.DEFAULT_COUNT)
        hard = PhaseConstraints(
            name="hard",
            allow_pits=True,
            allow_floor_height_shifts=True,
            max_gap_tiles=None,
            min_path_steps=int(proc.get("min_path_steps", 8)),
            max_path_steps=int(proc.get("max_path_steps", 14)),
            continue_weight=float(proc.get("continue_weight", 2.5)),
            pit_weight=float(proc.get("pit_weight", 4.0)),
            floor_height_shift_weight=float(
                proc.get("floor_height_shift_weight", 2.0)
            ),
        )
        slots = [("hard", hard, i) for i in range(1, n + 1)]

    level_names: list[str] = []
    phase_names: list[str] = []
    max_attempts = max(1, int(proc.get("pack_level_max_attempts", 8)))
    try:
        for index, (phase_name, phase, _idx) in enumerate(slots, start=1):
            level_name = f"Gen_{group}_{index:02d}_{phase_name}"
            sketch = None
            last_error: Exception | None = None
            base_seed = None if seed is None else int(seed) + index * 17
            for attempt in range(max_attempts):
                attempt_seed = (
                    None if base_seed is None else base_seed + attempt * 97
                )
                gen = ProceduralPlatformingGenerator(
                    seed=attempt_seed,
                    limits=limits,
                    phase=phase,
                    cfg=proc,
                )
                try:
                    sketch = gen.generate_sketch(level_name, difficulty=0.5)
                    break
                except ValueError as exc:
                    last_error = exc
                    continue
            if sketch is None:
                raise ValueError(
                    f"Failed to generate '{level_name}' after {max_attempts} attempts: "
                    f"{last_error}"
                ) from last_error
            level = importer.import_sketch(sketch)
            save_path = out_root / level_name / "level.json"
            level.save(custom_path=save_path)
            level_names.append(level_name)
            phase_names.append(phase_name)
    except (LevelSketchError, ValueError):
        if out_root.exists():
            shutil.rmtree(out_root, ignore_errors=True)
        raise

    if register_group is not None:
        register_group(group, level_names)

    return PackResult(
        group=group,
        level_names=level_names,
        phase_names=phase_names,
        path=out_root,
        seed=seed,
        curriculum=curriculum,
    )


def default_pack_group() -> str:
    return str(procedural_config.get("default_pack_group", "platforming_gen_v1"))
