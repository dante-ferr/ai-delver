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
    limits_to_jsonable,
)

__all__ = [
    "ALLOWED_ELEMENT_IDS",
    "LevelSketch",
    "LevelSketchError",
    "LevelSketchImporter",
    "PlatformingLimits",
    "PlatformingLimitsError",
    "compute_platforming_limits",
    "ensure_surrounding_walls",
    "limits_to_jsonable",
    "parse_level_sketch",
    "validate_level_sketch",
]
