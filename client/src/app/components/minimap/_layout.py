"""Layout math for fitting a level grid into the minimap canvas."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .minimap import Minimap


class MinimapLayout:
    """Computes scale, offsets, and wall set for the current canvas size."""

    def __init__(self, minimap: "Minimap"):
        self.minimap = minimap

    def compute(self) -> dict[str, Any] | None:
        m = self.minimap

        canvas_w = m.canvas.winfo_width()
        canvas_h = m.canvas.winfo_height()
        if canvas_w <= 1 or canvas_h <= 1:
            return None

        grid_w, grid_h = m.grid_size if m.grid_size else (27, 27)

        margin = 15
        available_w = canvas_w - 2 * margin
        available_h = canvas_h - 2 * margin

        scale_x = available_w / grid_w
        scale_y = available_h / grid_h
        scale = min(scale_x, scale_y)

        offset_x = margin + (available_w - grid_w * scale) / 2
        offset_y = margin

        wall_set = {(int(wx), int(wy)) for wx, wy in m.walls}
        max_diag = grid_w + grid_h - 2

        return {
            "grid_w": grid_w,
            "grid_h": grid_h,
            "scale": scale,
            "offset_x": offset_x,
            "offset_y": offset_y,
            "wall_set": wall_set,
            "max_diag": max_diag,
            "start_pos": m.start_pos,
            "goal_pos": m.goal_pos,
        }

    @staticmethod
    def tile_center(layout: dict[str, Any], x: int, y: int) -> tuple[float, float, float]:
        scale = layout["scale"]
        cx = layout["offset_x"] + (x + 0.5) * scale
        cy = layout["offset_y"] + (y + 0.5) * scale
        return cx, cy, scale / 2
