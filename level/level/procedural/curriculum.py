"""Named obstacle-type curriculum phases for procedural pack generation."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterator

from level.config import Config, procedural_config
from level.procedural.platforming_generator import PhaseConstraints


def load_phases(cfg: Config | None = None) -> list[PhaseConstraints]:
    """Parse ``[[phases]]`` tables from procedural platforming config."""
    source = cfg if cfg is not None else procedural_config
    raw_phases = source.get("phases", [])
    if not isinstance(raw_phases, list) or not raw_phases:
        return [PhaseConstraints(name="mixed")]

    phases: list[PhaseConstraints] = []
    for entry in raw_phases:
        if not isinstance(entry, dict):
            continue
        phases.append(_phase_from_dict(entry))
    return phases or [PhaseConstraints(name="mixed")]


def levels_per_phase(cfg: Config | None = None) -> int:
    source = cfg if cfg is not None else procedural_config
    return max(1, int(source.get("levels_per_phase", 2)))


def iter_curriculum_slots(
    *,
    count: int | None = None,
    cfg: Config | None = None,
) -> Iterator[tuple[str, PhaseConstraints, int]]:
    """Yield ``(level_suffix_stem, phase, index_in_phase)`` for a pack.

    When ``count`` is None, emit ``len(phases) * levels_per_phase`` slots.
    When ``count`` is set, cycle phases until ``count`` levels are produced.
    """
    source = cfg if cfg is not None else procedural_config
    phases = load_phases(source)
    per = levels_per_phase(source)
    if count is None:
        total = len(phases) * per
    else:
        total = max(1, int(count))

    produced = 0
    phase_idx = 0
    while produced < total:
        phase = phases[phase_idx % len(phases)]
        for i in range(1, per + 1):
            if produced >= total:
                return
            yield phase.name, phase, i
            produced += 1
        phase_idx += 1


def _phase_from_dict(entry: dict[str, Any]) -> PhaseConstraints:
    def _opt_int(key: str) -> int | None:
        if key not in entry or entry[key] is None:
            return None
        value = int(entry[key])
        # 0 means "use global / physics default" in the toml schema.
        return value if value != 0 else None

    def _opt_float(key: str) -> float | None:
        if key not in entry or entry[key] is None:
            return None
        return float(entry[key])

    phase = PhaseConstraints(
        name=str(entry.get("name", "unnamed")),
        allow_pits=bool(entry.get("allow_pits", True)),
        allow_floor_height_shifts=bool(entry.get("allow_floor_height_shifts", True)),
        max_gap_tiles=_opt_int("max_gap_tiles"),
        max_rise_tiles=_opt_int("max_rise_tiles"),
        max_fall_tiles=_opt_int("max_fall_tiles"),
        force_delta_h=(
            int(entry["force_delta_h"]) if "force_delta_h" in entry else None
        ),
        prefer_positive_delta=bool(entry.get("prefer_positive_delta", False)),
        prefer_negative_delta=bool(entry.get("prefer_negative_delta", False)),
        min_path_steps=_opt_int("min_path_steps"),
        max_path_steps=_opt_int("max_path_steps"),
        continue_weight=_opt_float("continue_weight"),
        pit_weight=_opt_float("pit_weight"),
        floor_height_shift_weight=_opt_float("floor_height_shift_weight"),
    )
    # flat_run sets max_gap_tiles=0 meaning no pits — already handled via allow_pits.
    if phase.name == "flat_run":
        phase = replace(phase, allow_pits=False, allow_floor_height_shifts=False)
    return phase
