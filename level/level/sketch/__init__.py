"""Simplified level sketches for agentic curriculum authoring."""

from .schema import (
    ALLOWED_ELEMENT_IDS,
    LevelSketch,
    LevelSketchError,
    parse_level_sketch,
    validate_level_sketch,
)
from .borders import ensure_surrounding_walls
from .importer import LevelSketchImporter
from .platforming_limits import (
    PlatformingLimits,
    PlatformingLimitsError,
    compute_platforming_limits,
    delver_height_tiles,
    jump_height_tiles,
    limits_to_jsonable,
    max_gap_tiles,
    max_gap_tiles_for_delta_height,
)

__all__ = [
    "ALLOWED_ELEMENT_IDS",
    "LevelSketch",
    "LevelSketchError",
    "LevelSketchImporter",
    "PlatformingLimits",
    "PlatformingLimitsError",
    "compute_platforming_limits",
    "delver_height_tiles",
    "ensure_surrounding_walls",
    "jump_height_tiles",
    "limits_to_jsonable",
    "max_gap_tiles",
    "max_gap_tiles_for_delta_height",
    "parse_level_sketch",
    "validate_level_sketch",
]
