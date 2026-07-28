"""Trajectory-aware minimap that overlays the delver path on Minimap."""

from __future__ import annotations

from typing import Any

from src.app.components.minimap import Minimap
from src.config import config

from .path_overlay import PathOverlay


class TrajectoryMinimap(Minimap):
    """Path visualizer with size-independent diagonal reveal + staggered tile grow."""

    TITLE = "Path Visualizer"

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._path_reveal_ms = int(config.PATH_VISUALIZER.PATH_REVEAL_MS)
        self.trajectory = None
        self._path_idx = 0
        self._path_batch = 1
        self.path_overlay = PathOverlay(self)
        self._pending_end_marker_only = False
        self._end_marker_delay_ticks = 0

    def _same_level_as(self, trajectory) -> bool:
        new_hash = getattr(trajectory, "level_hash", None) or ""
        return bool(self._level_hash) and bool(new_hash) and new_hash == self._level_hash

    def update_minimap(
        self,
        trajectory,
        grid_size,
        tile_size,
        walls,
        start_pos,
        goal_pos,
        *,
        animate: bool = True,
    ):
        """Refresh path visualizer.

        Same-level switches while tiles are still revealing keep the floor
        animation going and swap the path overlay instantly. Path-only
        animations are also replaced instantly (no wait). Idle same-level
        switches still play a path reveal.
        """
        if trajectory is not None and self._same_level_as(trajectory):
            if not self._tiles_done or (self._is_animating() and not self._path_done):
                self._replace_path_instant(
                    trajectory,
                    grid_size,
                    tile_size,
                    walls,
                    start_pos,
                    goal_pos,
                )
                return

        self._apply_minimap_update(
            trajectory,
            grid_size,
            tile_size,
            walls,
            start_pos,
            goal_pos,
            animate=animate,
        )

    def _replace_path_instant(
        self,
        trajectory,
        grid_size,
        tile_size,
        walls,
        start_pos,
        goal_pos,
    ) -> None:
        """Swap to a new run's path without interrupting tile reveal."""
        self.trajectory = trajectory
        self.grid_size = grid_size
        self.tile_size = tile_size
        self.walls = walls
        self.start_pos = start_pos
        self.goal_pos = goal_pos

        self.canvas.delete("path")
        self.canvas.delete("marker")

        if self._tiles_done and self._anim_after_id is not None:
            try:
                self.after_cancel(self._anim_after_id)
            except Exception:
                pass
            self._anim_after_id = None
            self._anim_gen += 1

        if self._tiles_done:
            layout = self._compute_layout()
        elif self._layout is not None:
            layout = self._overlay_path_on_layout(self._layout)
        else:
            layout = self._compute_layout()

        if layout is None:
            self._path_done = True
            return

        self._layout = layout
        self.path_overlay.draw_full_path(layout)
        self._path_done = True
        self._pending_end_marker_only = False
        self._end_marker_delay_ticks = 0

    def _overlay_path_on_layout(self, base: dict[str, Any]) -> dict[str, Any]:
        """Reuse current floor layout metrics; refresh path points only."""
        layout = dict(base)
        if not self.trajectory:
            layout["canvas_points"] = []
            layout["victorious"] = False
            return layout

        grid_w, grid_h = layout["grid_w"], layout["grid_h"]
        tile_w, tile_h = self.tile_size if self.tile_size else (16, 16)
        scale = layout["scale"]
        offset_x = layout["offset_x"]
        offset_y = layout["offset_y"]

        path_points = []
        for snapshot in self.trajectory.frame_snapshots:
            for entity in snapshot.entities:
                if entity.entity_id.lower().startswith("delver"):
                    path_points.append(entity.position)
                    break

        canvas_points = []
        for px, py in path_points:
            gx = (px - tile_w / 2) / tile_w
            gy = (grid_h * tile_h - (py - tile_h / 2)) / tile_h
            cx = offset_x + gx * scale
            cy = offset_y + gy * scale
            canvas_points.append((cx, cy))

        layout["canvas_points"] = canvas_points
        layout["victorious"] = bool(self.trajectory.victorious)
        return layout

    def _apply_minimap_update(
        self,
        trajectory,
        grid_size,
        tile_size,
        walls,
        start_pos,
        goal_pos,
        *,
        animate: bool,
    ):
        self.trajectory = trajectory
        new_hash = getattr(trajectory, "level_hash", None) or ""
        same_level = self.set_level(
            grid_size,
            tile_size,
            walls,
            start_pos,
            goal_pos,
            level_hash=new_hash or None,
            animate=animate,
        )
        if same_level:
            self.canvas.delete("path")
            self.canvas.delete("marker")
            self.path_overlay.start_path_only()
            return

        if not animate:
            layout = self._layout or self._compute_layout()
            if layout is not None:
                self._layout = layout
                self._path_done = True

    def draw_minimap(self):
        """Synchronous full redraw (used after resize)."""
        if self._is_animating() or self._waiting_for_canvas:
            return
        self._sync_draw_minimap()

    def _sync_draw_minimap(self):
        self._cancel_animation()
        self.canvas.delete("all")
        self._growing = []
        self._has_drawn_content = False
        self._tiles_complete = False
        if not self.trajectory:
            self._layout = None
            return

        layout = self._compute_layout()
        if layout is None:
            self._layout = None
            return

        self._layout = layout
        self._draw_full(layout)
        self._has_drawn_content = True
        self._tiles_complete = True
        self._tiles_done = True
        self._path_done = True
        self._level_hash = (
            getattr(self.trajectory, "level_hash", None) or self._level_hash
        )

    def _compute_layout(self) -> dict[str, Any] | None:
        layout = super()._compute_layout()
        if layout is None or not self.trajectory:
            return layout
        return self._overlay_path_on_layout(layout)

    def _on_reveal_started(self, layout: dict[str, Any]) -> None:
        self.path_overlay.prepare_path_anim(layout)

    def _on_draw_full(self, layout: dict[str, Any]) -> None:
        self.path_overlay.draw_full_path(layout)

    def _on_anim_tick(self, layout: dict[str, Any]) -> None:
        if not self._path_done:
            self.path_overlay.advance_path_reveal(layout)

    def _clear_state(self):
        super()._clear_state()
        self.trajectory = None
