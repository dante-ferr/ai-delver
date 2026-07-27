"""Tile and start/goal marker drawing for the minimap."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ._layout import MinimapLayout

if TYPE_CHECKING:
    from .minimap import Minimap


class MinimapTileDraw:
    """Draws floor/wall tiles and start/goal markers onto the canvas."""

    def __init__(self, minimap: "Minimap"):
        self.minimap = minimap

    def spawn_tile(self, layout: dict[str, Any], x: int, y: int) -> None:
        """Create a tile at size 0 (center) and register it for staggered grow."""
        m = self.minimap
        d = x + y
        tag = f"diag_{d}"
        is_wall = (x, y) in layout["wall_set"]
        cx, cy, half = MinimapLayout.tile_center(layout, x, y)

        if is_wall:
            fill, outline = "#4f4f4f", "#3e3e3e"
        else:
            fill, outline = "#171717", "#2a2a2a"

        item_id = m.canvas.create_rectangle(
            cx,
            cy,
            cx,
            cy,
            outline=outline,
            fill=fill,
            width=1,
            tags=(tag, "tile"),
        )
        m._growing.append(
            {
                "id": item_id,
                "cx": cx,
                "cy": cy,
                "half": half,
                "age": 0,
                "shrinking": False,
            }
        )

    def draw_tile_full(self, layout: dict[str, Any], x: int, y: int) -> None:
        """Immediate full-size tile (sync redraw path)."""
        m = self.minimap
        d = x + y
        tag = f"diag_{d}"
        cx, cy, half = MinimapLayout.tile_center(layout, x, y)
        is_wall = (x, y) in layout["wall_set"]
        if is_wall:
            fill, outline = "#4f4f4f", "#3e3e3e"
        else:
            fill, outline = "#171717", "#2a2a2a"
        m.canvas.create_rectangle(
            cx - half,
            cy - half,
            cx + half,
            cy + half,
            outline=outline,
            fill=fill,
            width=1,
            tags=(tag, "tile"),
        )

    def draw_diagonal(self, layout: dict[str, Any], d: int, grow: bool = False) -> None:
        grid_w = layout["grid_w"]
        grid_h = layout["grid_h"]
        for x in range(grid_w):
            y = d - x
            if 0 <= y < grid_h:
                if grow:
                    self.spawn_tile(layout, x, y)
                else:
                    self.draw_tile_full(layout, x, y)

    def draw_goal_marker(self, layout: dict[str, Any]) -> None:
        if not layout["goal_pos"]:
            return
        m = self.minimap
        gx, gy = layout["goal_pos"]
        scale = layout["scale"]
        cx = layout["offset_x"] + (gx + 0.5) * scale
        cy = layout["offset_y"] + (gy + 0.5) * scale
        r = max(4.0, scale * 0.4)
        m.canvas.create_oval(
            cx - r,
            cy - r,
            cx + r,
            cy + r,
            fill="#f59e0b",
            outline="#d97706",
            width=2,
            tags=("marker",),
        )
        m.canvas.create_text(
            cx,
            cy,
            text="G",
            fill="#ffffff",
            font=("Arial", int(max(6, scale * 0.5)), "bold"),
            tags=("marker",),
        )

    def draw_start_marker(self, layout: dict[str, Any]) -> None:
        if not layout["start_pos"]:
            return
        m = self.minimap
        sx, sy = layout["start_pos"]
        scale = layout["scale"]
        cx = layout["offset_x"] + (sx + 0.5) * scale
        cy = layout["offset_y"] + (sy + 0.5) * scale
        r = max(4.0, scale * 0.4)
        m.canvas.create_oval(
            cx - r,
            cy - r,
            cx + r,
            cy + r,
            fill="#10b981",
            outline="#059669",
            width=2,
            tags=("marker",),
        )
        m.canvas.create_text(
            cx,
            cy,
            text="S",
            fill="#ffffff",
            font=("Arial", int(max(6, scale * 0.5)), "bold"),
            tags=("marker",),
        )
