"""Programmatic level-sketch layout rules (borders, etc.)."""

from __future__ import annotations

from level.sketch.schema import LevelSketch


def ensure_surrounding_walls(sketch: LevelSketch) -> LevelSketch:
    """Return a copy of ``sketch`` with ``platform`` on every perimeter cell.

    Interior cells are unchanged. Existing perimeter platforms are preserved;
    other IDs on the border (e.g. delver on the floor) are kept and ``platform``
    is added if missing.
    """
    if sketch.width < 2 or sketch.height < 2:
        # Degenerate grids: treat every cell as perimeter.
        pass

    new_rows: list[list[tuple[str, ...]]] = []
    for y, row in enumerate(sketch.cells):
        new_row: list[tuple[str, ...]] = []
        for x, elements in enumerate(row):
            if _is_perimeter(x, y, sketch.width, sketch.height):
                if "platform" in elements:
                    new_row.append(elements)
                else:
                    new_row.append(("platform",) + elements)
            else:
                new_row.append(elements)
        new_rows.append(new_row)

    return LevelSketch(
        name=sketch.name,
        width=sketch.width,
        height=sketch.height,
        cells=tuple(tuple(row) for row in new_rows),
    )


def _is_perimeter(x: int, y: int, width: int, height: int) -> bool:
    return x == 0 or y == 0 or x == width - 1 or y == height - 1
