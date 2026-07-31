"""Procedural platforming level generation (sketch → importer)."""

from .curriculum import iter_curriculum_slots, levels_per_phase, load_phases
from .pack import PackResult, default_pack_group, generate_platforming_pack
from .platforming_generator import (
    PathShape,
    PhaseConstraints,
    PlatformSeg,
    ProceduralPlatformingGenerator,
    max_horizontal_gap,
    path_has_direction_change,
)

__all__ = [
    "PackResult",
    "PathShape",
    "PhaseConstraints",
    "PlatformSeg",
    "ProceduralPlatformingGenerator",
    "default_pack_group",
    "generate_platforming_pack",
    "iter_curriculum_slots",
    "levels_per_phase",
    "load_phases",
    "max_horizontal_gap",
    "path_has_direction_change",
]
