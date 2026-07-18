"""Parse and validate agentic level-sketch JSON."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from level.config import MAX_GRID_SIZE, MIN_GRID_SIZE
from level.exceptions import LevelError

ALLOWED_ELEMENT_IDS = frozenset({"platform", "delver", "goal"})


class LevelSketchError(LevelError):
    """Raised when a level sketch is invalid or cannot be imported."""


@dataclass(frozen=True)
class LevelSketch:
    """Validated dense grid sketch ready for import."""

    name: str
    width: int
    height: int
    # cells[y][x] -> tuple of element ids at that tile (may be empty)
    cells: tuple[tuple[tuple[str, ...], ...], ...]


def parse_level_sketch(data: Any) -> LevelSketch:
    """Parse raw JSON data into a validated LevelSketch."""
    if not isinstance(data, dict):
        raise LevelSketchError("Sketch root must be a JSON object.")

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise LevelSketchError("Sketch 'name' must be a non-empty string.")

    grid_size = data.get("grid_size")
    if (
        not isinstance(grid_size, (list, tuple))
        or len(grid_size) != 2
        or not all(isinstance(v, int) and not isinstance(v, bool) for v in grid_size)
    ):
        raise LevelSketchError("Sketch 'grid_size' must be [width, height] integers.")

    width, height = int(grid_size[0]), int(grid_size[1])
    min_w, min_h = MIN_GRID_SIZE
    max_w, max_h = MAX_GRID_SIZE
    if width < min_w or height < min_h or width > max_w or height > max_h:
        raise LevelSketchError(
            f"Sketch grid_size {width}x{height} is outside allowed bounds "
            f"{min_w}x{min_h}..{max_w}x{max_h}."
        )

    cells_raw = data.get("cells")
    if not isinstance(cells_raw, list):
        raise LevelSketchError("Sketch 'cells' must be a 2D array (list of rows).")
    if len(cells_raw) != height:
        raise LevelSketchError(
            f"Sketch 'cells' has {len(cells_raw)} rows but grid_size height is {height}."
        )

    normalized: list[tuple[tuple[str, ...], ...]] = []
    for y, row in enumerate(cells_raw):
        if not isinstance(row, list):
            raise LevelSketchError(f"Sketch row {y} must be a list.")
        if len(row) != width:
            raise LevelSketchError(
                f"Sketch row {y} has {len(row)} columns but grid_size width is {width}."
            )
        normalized_row: list[tuple[str, ...]] = []
        for x, cell in enumerate(row):
            normalized_row.append(_normalize_cell(cell, x, y))
        normalized.append(tuple(normalized_row))

    sketch = LevelSketch(
        name=name.strip(),
        width=width,
        height=height,
        cells=tuple(normalized),
    )
    validate_level_sketch(sketch)
    return sketch


def validate_level_sketch(sketch: LevelSketch) -> None:
    """Ensure element rules match editor/runtime concurrence semantics.

    ``delver`` / ``goal`` cells are bottom-left anchors; their tile footprints
    (from the size registry) must stay interior and clear of platforms.
    """
    from level.world_object_sizes import world_object_size
    from pytiling import footprint_positions

    delver_count = 0
    goal_count = 0
    delver_anchor: tuple[int, int] | None = None
    goal_anchor: tuple[int, int] | None = None

    # Build a quick lookup of which cells contain which ids.
    cell_ids: dict[tuple[int, int], set[str]] = {}
    for y, row in enumerate(sketch.cells):
        for x, elements in enumerate(row):
            seen_in_cell: set[str] = set()
            for element_id in elements:
                if element_id not in ALLOWED_ELEMENT_IDS:
                    raise LevelSketchError(
                        f"Unknown element id '{element_id}' at ({x}, {y}). "
                        f"Allowed: {sorted(ALLOWED_ELEMENT_IDS)}."
                    )
                if element_id in seen_in_cell:
                    raise LevelSketchError(
                        f"Duplicate element id '{element_id}' in cell ({x}, {y})."
                    )
                seen_in_cell.add(element_id)
                if element_id == "delver":
                    delver_count += 1
                    delver_anchor = (x, y)
                elif element_id == "goal":
                    goal_count += 1
                    goal_anchor = (x, y)

            cell_ids[(x, y)] = seen_in_cell

            # platforms ↔ essentials are concurrent: one position cannot hold both.
            has_platform = "platform" in seen_in_cell
            has_world = bool(seen_in_cell & {"delver", "goal"})
            if has_platform and has_world:
                raise LevelSketchError(
                    f"Cell ({x}, {y}) cannot combine 'platform' with delver/goal "
                    "(concurrent layers). Place the world object in an empty cell "
                    "above a floor platform."
                )

            on_perimeter = (
                x == 0 or y == 0 or x == sketch.width - 1 or y == sketch.height - 1
            )
            if on_perimeter and has_world:
                raise LevelSketchError(
                    f"Cell ({x}, {y}) places delver/goal on the perimeter. "
                    "Keep spawns/goals interior so surrounding walls can seal the map."
                )

    if delver_count != 1:
        raise LevelSketchError(
            f"Sketch must contain exactly one 'delver' (found {delver_count})."
        )
    if goal_count != 1:
        raise LevelSketchError(
            f"Sketch must contain exactly one 'goal' (found {goal_count})."
        )

    assert delver_anchor is not None and goal_anchor is not None

    def _validate_footprint(name: str, anchor: tuple[int, int]) -> set[tuple[int, int]]:
        size = world_object_size(name)
        cells = footprint_positions(anchor, size)
        for cx, cy in cells:
            if cx < 0 or cy < 0 or cx >= sketch.width or cy >= sketch.height:
                raise LevelSketchError(
                    f"'{name}' at {anchor} with size {size} extends out of bounds "
                    f"(cell ({cx}, {cy}))."
                )
            on_perimeter = (
                cx == 0
                or cy == 0
                or cx == sketch.width - 1
                or cy == sketch.height - 1
            )
            if on_perimeter:
                raise LevelSketchError(
                    f"'{name}' footprint at {anchor} (size {size}) touches perimeter "
                    f"cell ({cx}, {cy}). Leave room above/beside the standing cell."
                )
            if "platform" in cell_ids.get((cx, cy), set()):
                raise LevelSketchError(
                    f"'{name}' footprint at {anchor} (size {size}) overlaps platform "
                    f"at ({cx}, {cy})."
                )
        return set(cells)

    delver_cells = _validate_footprint("delver", delver_anchor)
    goal_cells = _validate_footprint("goal", goal_anchor)
    overlap = delver_cells & goal_cells
    if overlap:
        raise LevelSketchError(
            f"Delver and goal footprints overlap at {sorted(overlap)}."
        )


def _normalize_cell(cell: Any, x: int, y: int) -> tuple[str, ...]:
    if cell is None or cell == "":
        return ()
    if isinstance(cell, str):
        value = cell.strip()
        return (value,) if value else ()
    if isinstance(cell, list):
        ids: list[str] = []
        for item in cell:
            if item is None or item == "":
                continue
            if not isinstance(item, str) or not item.strip():
                raise LevelSketchError(
                    f"Cell ({x}, {y}) array entries must be non-empty strings."
                )
            ids.append(item.strip())
        return tuple(ids)
    raise LevelSketchError(
        f"Cell ({x}, {y}) must be null, a string, or an array of strings."
    )
