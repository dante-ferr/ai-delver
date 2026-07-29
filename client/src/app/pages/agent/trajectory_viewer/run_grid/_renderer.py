from __future__ import annotations

import customtkinter as ctk

from app.fonts import app_font, canvas_font
from typing import TYPE_CHECKING

from ._config import color_for_level_hash

if TYPE_CHECKING:
    from .run_grid import RunGrid

class RunGridRenderer:
    def __init__(self, grid: "RunGrid"):
        self.grid = grid

    def cell_pitch(self) -> int:
        g = self.grid
        return g.cell_size + g.cell_gap

    def compute_cols(self) -> int:
        g = self.grid
        width = max(1, int(g.canvas.winfo_width()))
        pitch = g.renderer.cell_pitch()
        cols = max(1, (width - 4) // pitch)
        g._cols = cols
        return cols

    def debounced_canvas_redraw(self):
        g = self.grid
        g._canvas_redraw_after_id = None
        g.renderer.redraw()

    def ensure_index_visible(self, real_index: int) -> bool:
        """Scroll so index is in view. Returns True if scroll row changed."""
        g = self.grid
        slot = g.renderer.slot_for_index(real_index)
        if slot is None:
            return False
        cols = g.renderer.compute_cols()
        row = slot // cols
        view_rows = max(1, int(g.canvas.winfo_height()) // g.row_height)
        old_scroll = g._scroll_row
        if row < g._scroll_row:
            g._scroll_row = row
        elif row >= g._scroll_row + view_rows:
            g._scroll_row = max(0, row - view_rows + 1)
        return g._scroll_row != old_scroll

    def cell_rect_for_index(self, real_index: int) -> tuple[float, float, float, float] | None:
        """Canvas coords for a run cell, or None if not in the current viewport."""
        g = self.grid
        slot = g.renderer.slot_for_index(real_index)
        if slot is None:
            return None
        cols = g.renderer.compute_cols()
        row = slot // cols
        col = slot % cols
        view_rows = max(1, int(g.canvas.winfo_height()) // g.row_height)
        if row < g._scroll_row or row >= g._scroll_row + view_rows:
            return None
        pitch = g.renderer.cell_pitch()
        x0 = 2 + col * pitch
        y0 = (row - g._scroll_row) * g.row_height + 2
        x1 = x0 + g.cell_size
        y1 = y0 + g.cell_size
        return x0, y0, x1, y1

    def move_selection_ring(self, real_index: int | None) -> None:
        """Move the selection overlay without wiping the grid."""
        g = self.grid
        g.canvas.delete("selection_ring")
        if real_index is None:
            return
        rect = g.renderer.cell_rect_for_index(real_index)
        if rect is None:
            return
        x0, y0, x1, y1 = rect
        g.canvas.create_rectangle(
            x0 - 1,
            y0 - 1,
            x1 + 1,
            y1 + 1,
            fill="",
            outline=g.renderer.selection_ring_color(),
            width=2,
            tags=("selection_ring",),
        )

    def index_at_xy(self, x: float, y: float) -> int | None:
        g = self.grid
        cols = g.renderer.compute_cols()
        pitch = g.renderer.cell_pitch()
        col = int((x - 2) // pitch)
        row = int(y // g.row_height) + g._scroll_row
        if col < 0 or col >= cols or row < 0:
            return None
        slot = row * cols + col
        if 0 <= slot < len(g._visible_indices):
            return g._visible_indices[slot]
        return None

    # ----------------------------------------------------------------- draw

    def on_canvas_configure(self, _event=None):
        g = self.grid
        if g._canvas_redraw_after_id is not None:
            try:
                g.after_cancel(g._canvas_redraw_after_id)
            except Exception:
                pass
        g._canvas_redraw_after_id = g.after(40, g.renderer.debounced_canvas_redraw)

    def redraw(self):
        g = self.grid
        g.canvas.delete("all")
        cols = g.renderer.compute_cols()
        width = max(1, int(g.canvas.winfo_width()))
        height = max(1, int(g.canvas.winfo_height()))
        view_rows = max(1, height // g.row_height)
        total_rows = g.renderer.total_rows()

        # Scrollbar fraction
        if total_rows <= view_rows:
            g.scrollbar.set(0, 1)
            g._scroll_row = 0
        else:
            first = g._scroll_row / total_rows
            last = (g._scroll_row + view_rows) / total_rows
            g.scrollbar.set(first, min(1.0, last))

        if not g._visible_indices:
            g.canvas.create_text(
                width / 2,
                height / 2,
                text="No runs to display",
                fill="#6b7280",
                font=canvas_font(11),
            )
            return

        start_row = max(0, g._scroll_row - g.overscan_rows)
        end_row = min(total_rows, g._scroll_row + view_rows + g.overscan_rows)
        pitch = g.renderer.cell_pitch()
        bg = g.canvas.cget("bg")

        # Lazy-load only the slots about to be painted.
        slots_needed: list[int] = []
        for row in range(start_row, end_row):
            for col in range(cols):
                slot = row * cols + col
                if slot >= len(g._visible_indices):
                    break
                slots_needed.append(g._visible_indices[slot])
        g.data.ensure_visible_entries(slots_needed)

        prev_cycle = None
        has_prev_cycle = False
        for row in range(start_row, end_row):
            for col in range(cols):
                slot = row * cols + col
                if slot >= len(g._visible_indices):
                    break
                real_index = g._visible_indices[slot]
                entry = g.data.entry(real_index) or {}
                x0 = 2 + col * pitch
                y0 = (row - g._scroll_row) * g.row_height + 2
                x1 = x0 + g.cell_size
                y1 = y0 + g.cell_size

                cycle = entry.get("cycle")
                if (
                    cycle is not None
                    and has_prev_cycle
                    and cycle != prev_cycle
                    and col == 0
                ):
                    sep_y = y0 - max(1, g.cell_gap)
                    g.canvas.create_line(
                        2, sep_y, width - 2, sep_y, fill="#374151", width=1
                    )
                if cycle is not None:
                    prev_cycle = cycle
                    has_prev_cycle = True

                level_hash = str(entry.get("level_hash", "") or "")
                color = color_for_level_hash(level_hash) if entry else "#4b5563"
                if not entry:
                    color = "#4b5563"
                victorious = bool(entry.get("victorious"))
                is_play = entry.get("kind") == "play"

                if entry and victorious:
                    g.canvas.create_rectangle(
                        x0, y0, x1, y1, fill=color, outline=color, width=1, tags=("cell",)
                    )
                else:
                    g.canvas.create_rectangle(
                        x0, y0, x1, y1, fill=bg, outline=color, width=1, tags=("cell",)
                    )

                if is_play:
                    g.canvas.create_rectangle(
                        x0 + 1,
                        y0 + 1,
                        x1 - 1,
                        y1 - 1,
                        fill="",
                        outline=g.play_border_color,
                        width=1,
                        dash=(2, 1),
                    )

                if real_index == g._selected_index:
                    ring = g.renderer.selection_ring_color()
                    g.canvas.create_rectangle(
                        x0 - 1,
                        y0 - 1,
                        x1 + 1,
                        y1 + 1,
                        fill="",
                        outline=ring,
                        width=2,
                        tags=("selection_ring",),
                    )

    def selection_ring_color(self) -> str:
        g = self.grid
        if g._live_mode:
            return g.live_color if g._pulse_on else g.selection_color
        return g.selection_color

    def slot_for_index(self, real_index: int) -> int | None:
        g = self.grid
        try:
            return g._visible_indices.index(real_index)
        except ValueError:
            return None

    def total_rows(self) -> int:
        g = self.grid
        n = len(g._visible_indices)
        if n <= 0:
            return 1
        return max(1, (n + g._cols - 1) // g._cols)

    def update_selection_ring(self) -> None:
        g = self.grid
        """Pulse live selection without wiping the whole grid canvas."""
        items = g.canvas.find_withtag("selection_ring")
        if not items:
            return
        color = g.renderer.selection_ring_color()
        for item_id in items:
            try:
                g.canvas.itemconfigure(item_id, outline=color)
            except Exception:
                pass
