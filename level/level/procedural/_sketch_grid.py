"""Dynamically growing sketch grid with platform and clearance markers."""

from __future__ import annotations

from enum import IntEnum


class CellKind(IntEnum):
    EMPTY = 0
    PLATFORM = 1
    CLEARANCE = 2


class SketchGrid:
    """Sparse cell grid that expands as platforms / clearance are painted."""

    def __init__(self) -> None:
        self._cells: dict[tuple[int, int], CellKind] = {}
        self.pit_columns: set[int] = set()
        self.min_x = 0
        self.max_x = -1
        self.min_y = 0
        self.max_y = -1

    def __bool__(self) -> bool:
        return bool(self._cells)

    def get(self, x: int, y: int) -> CellKind:
        return self._cells.get((x, y), CellKind.EMPTY)

    def is_platform(self, x: int, y: int) -> bool:
        return self.get(x, y) == CellKind.PLATFORM

    def is_clearance(self, x: int, y: int) -> bool:
        return self.get(x, y) == CellKind.CLEARANCE

    def is_blocked_for_platform(self, x: int, y: int) -> bool:
        """True if painting a platform here would violate enforced empty clearance."""
        kind = self.get(x, y)
        return kind == CellKind.CLEARANCE or kind == CellKind.PLATFORM

    def paint_platform(self, x: int, y: int) -> bool:
        """Paint a platform cell. Fails if the cell is already clearance."""
        if self.get(x, y) == CellKind.CLEARANCE:
            return False
        self._cells[(x, y)] = CellKind.PLATFORM
        self._expand(x, y)
        return True

    def paint_clearance(self, x: int, y: int) -> None:
        """Mark enforced empty clearance; never overwrites platforms."""
        if self.get(x, y) == CellKind.PLATFORM:
            return
        self._cells[(x, y)] = CellKind.CLEARANCE
        self._expand(x, y)

    def platform_cells(self) -> set[tuple[int, int]]:
        return {pos for pos, kind in self._cells.items() if kind == CellKind.PLATFORM}

    def clearance_cells(self) -> set[tuple[int, int]]:
        return {pos for pos, kind in self._cells.items() if kind == CellKind.CLEARANCE}

    def bounds(self) -> tuple[int, int, int, int]:
        """Return (min_x, min_y, max_x, max_y) inclusive, or zeros if empty."""
        if not self._cells:
            return 0, 0, 0, 0
        return self.min_x, self.min_y, self.max_x, self.max_y

    def _expand(self, x: int, y: int) -> None:
        if len(self._cells) == 1:
            self.min_x = self.max_x = x
            self.min_y = self.max_y = y
            return
        self.min_x = min(self.min_x, x)
        self.max_x = max(self.max_x, x)
        self.min_y = min(self.min_y, y)
        self.max_y = max(self.max_y, y)
