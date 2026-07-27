"""Trajectory path overlay helpers for TrajectoryMinimap."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.fonts import canvas_font
from src.app.components.minimap._tile_animation import MinimapTileAnimation

if TYPE_CHECKING:
    from ._trajectory_minimap import TrajectoryMinimap


class PathOverlay:
    """Draws and animates the delver path + end marker on a TrajectoryMinimap."""

    def __init__(self, minimap: "TrajectoryMinimap"):
        self.minimap = minimap

    def draw_end_marker(self, layout: dict[str, Any]) -> None:
        canvas_points = layout.get("canvas_points") or []
        if not canvas_points:
            return
        m = self.minimap
        ex, ey = canvas_points[-1]
        scale = layout["scale"]
        r = max(5.0, scale * 0.4)
        end_color = "#10b981" if layout.get("victorious") else "#ef4444"
        m.canvas.create_oval(
            ex - r,
            ey - r,
            ex + r,
            ey + r,
            fill=end_color,
            outline="#ffffff",
            width=2,
            tags=("marker",),
        )
        marker_text = "🏆" if layout.get("victorious") else "💀"
        m.canvas.create_text(
            ex,
            ey,
            text=marker_text,
            font=canvas_font(int(max(7, scale * 0.5))),
            tags=("marker",),
        )

    def draw_path_batch(
        self, layout: dict[str, Any], start_idx: int, batch_size: int
    ) -> int:
        points = layout.get("canvas_points") or []
        if len(points) < 2:
            return 0

        end_idx = min(start_idx + batch_size, len(points) - 1)
        if end_idx <= start_idx:
            return 0

        coords = []
        for i in range(start_idx, end_idx + 1):
            coords.extend(points[i])

        self.minimap.canvas.create_line(
            *coords,
            fill="#3b82f6",
            width=3,
            tags=("path",),
        )
        return end_idx - start_idx

    def draw_full_path(self, layout: dict[str, Any]) -> None:
        points = layout.get("canvas_points") or []
        if len(points) > 1:
            coords = []
            for p in points:
                coords.extend(p)
            self.minimap.canvas.create_line(
                *coords,
                fill="#3b82f6",
                width=3,
                tags=("path",),
            )
        self.draw_end_marker(layout)

    def prepare_path_anim(self, layout: dict[str, Any]) -> None:
        m = self.minimap
        points = layout.get("canvas_points") or []
        segments = max(0, len(points) - 1)
        if segments == 0:
            m._path_done = True
            self.draw_end_marker(layout)
            return

        m._path_batch = MinimapTileAnimation.items_per_tick(
            segments, m._path_reveal_ms, m._tick_ms
        )
        m._path_idx = 0
        m._path_done = False

    def advance_path_reveal(self, layout: dict[str, Any]) -> None:
        m = self.minimap
        points = layout.get("canvas_points") or []
        if len(points) < 2:
            m._path_done = True
            self.draw_end_marker(layout)
            return

        drawn = self.draw_path_batch(layout, m._path_idx, m._path_batch)
        if drawn <= 0:
            m._path_done = True
            self.draw_end_marker(layout)
            return

        m._path_idx += drawn

        if m._path_idx >= len(points) - 1:
            m._path_done = True
            self.draw_end_marker(layout)

    def start_path_only(self) -> None:
        """Animate path only (same level as previous trajectory)."""
        m = self.minimap
        layout = m._compute_layout()
        if layout is None:
            m._layout = None
            return

        m._layout = layout
        m._has_drawn_content = True
        m._tiles_done = True
        m._growing = []

        m.tile_draw.draw_goal_marker(layout)
        m.tile_draw.draw_start_marker(layout)
        self.prepare_path_anim(layout)

        if m._path_done:
            m._anim_after_id = None
            return
        m._schedule_tick()
