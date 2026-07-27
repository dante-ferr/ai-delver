"""Reusable level overview minimap with diagonal reveal / wipe animations."""

from __future__ import annotations

from typing import Any

import customtkinter as ctk

from src.config import config

from ._layout import MinimapLayout
from ._resize import MinimapResize
from ._tile_animation import MinimapTileAnimation
from ._tile_draw import MinimapTileDraw


class Minimap(ctk.CTkFrame):
    """Level overview with size-independent diagonal reveal + staggered tile grow."""

    TITLE = "Minimap"

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="#2b2b2b", corner_radius=8, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        pv = config.PATH_VISUALIZER
        self._tick_ms = int(pv.TICK_MS)
        self._tile_reveal_ms = int(pv.TILE_REVEAL_MS)
        self._tile_wipe_ms = int(pv.TILE_WIPE_MS)
        self._grow_frames = int(pv.GROW_FRAMES)
        self._debounce_ms = int(pv.DEBOUNCE_MS)

        self.grid_size = None
        self.tile_size = None
        self.walls = []
        self.start_pos = None
        self.goal_pos = None

        self._anim_after_id = None
        self._configure_after_id = None
        self._layout = None
        self._has_drawn_content = False
        self._tiles_complete = False
        self._growing = []
        self._level_hash = None
        self._anim_gen = 0
        self._tiles_done = True
        self._path_done = True
        self._tile_next_d = 0
        self._diags_per_tick = 1

        self.layout_helper = MinimapLayout(self)
        self.tile_draw = MinimapTileDraw(self)
        self.tile_animation = MinimapTileAnimation(self)
        self.resize = MinimapResize(self)

        self.minimap_title = ctk.CTkLabel(
            self, text=self.TITLE, font=ctk.CTkFont(size=14, weight="bold")
        )
        self.minimap_title.grid(row=0, column=0, padx=12, pady=(12, 4), sticky="w")

        self.canvas = ctk.CTkCanvas(self, bg="#2b2b2b", highlightthickness=0)
        self.canvas.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        self.canvas.bind("<Configure>", self.resize.on_configure)

    def set_level(
        self,
        grid_size,
        tile_size,
        walls,
        start_pos,
        goal_pos,
        level_hash: str | None = None,
    ) -> bool:
        """Load level geometry. Returns True if the floor was kept (same hash)."""
        self._cancel_animation()
        new_hash = level_hash or ""
        same_level = (
            bool(new_hash)
            and new_hash == self._level_hash
            and self._tiles_complete
        )

        self.grid_size = grid_size
        self.tile_size = tile_size
        self.walls = walls
        self.start_pos = start_pos
        self.goal_pos = goal_pos
        self._level_hash = new_hash or None
        self._growing = []

        if same_level:
            return True

        self.canvas.delete("all")
        self._has_drawn_content = False
        self._tiles_complete = False
        self.tile_animation.start_reveal()
        return False

    def reset_to_default(self):
        self._cancel_animation()
        if self._has_drawn_content and self._layout is not None:
            self.tile_animation.start_wipe()
            return

        self._clear_state()
        self.canvas.delete("all")
        self._growing = []
        self._has_drawn_content = False
        self._tiles_complete = False

    def clear(self):
        """Hard-clear without wipe animation."""
        self._cancel_animation()
        self.resize.cancel()
        self._clear_state()
        self.canvas.delete("all")
        self._growing = []
        self._has_drawn_content = False
        self._tiles_complete = False

    def draw_minimap(self):
        """Synchronous full redraw (used after resize)."""
        self._cancel_animation()
        self.canvas.delete("all")
        self._growing = []
        self._has_drawn_content = False
        self._tiles_complete = False
        if self.grid_size is None and self._level_hash is None:
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

    def _compute_layout(self) -> dict[str, Any] | None:
        return self.layout_helper.compute()

    def _draw_full(self, layout: dict[str, Any]) -> None:
        """Synchronous full draw of grid, walls, and markers."""
        max_diag = layout["max_diag"]
        for d in range(max_diag + 1):
            self.tile_draw.draw_diagonal(layout, d, grow=False)

        self.tile_draw.draw_goal_marker(layout)
        self.tile_draw.draw_start_marker(layout)
        self._on_draw_full(layout)

    def _on_reveal_started(self, layout: dict[str, Any]) -> None:
        """Hook for subclasses (e.g. path reveal) after markers are drawn."""
        self._path_done = True

    def _on_draw_full(self, layout: dict[str, Any]) -> None:
        """Hook for subclasses to draw overlays on sync redraw."""

    def _on_anim_tick(self, layout: dict[str, Any]) -> None:
        """Hook for subclasses to advance overlays each animation tick."""

    def _cancel_animation(self):
        if self._anim_after_id is not None:
            try:
                self.after_cancel(self._anim_after_id)
            except Exception:
                pass
            self._anim_after_id = None
        self._anim_gen += 1
        self._tiles_done = True
        self._path_done = True
        self._growing = []

    def _schedule_tick(self):
        gen = self._anim_gen
        self._anim_after_id = self.after(self._tick_ms, lambda: self._anim_tick(gen))

    def _anim_tick(self, gen: int):
        if gen != self._anim_gen:
            return

        layout = self._layout
        if layout is None:
            self._anim_after_id = None
            return

        if not self._tiles_done:
            self.tile_animation.advance_tile_reveal(layout)

        self._on_anim_tick(layout)

        self.canvas.tag_raise("path")
        self.canvas.tag_raise("marker")

        if gen != self._anim_gen:
            return

        if not self._tiles_done or not self._path_done:
            self._schedule_tick()
        else:
            self._anim_after_id = None

    def _clear_state(self):
        self.grid_size = None
        self.tile_size = None
        self.walls = []
        self.start_pos = None
        self.goal_pos = None
        self._layout = None
        self._growing = []
        self._level_hash = None
        self._tiles_complete = False
