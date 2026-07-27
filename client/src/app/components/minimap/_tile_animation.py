"""Diagonal reveal, wipe, and staggered grow/shrink for minimap tiles."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .minimap import Minimap


class MinimapTileAnimation:
    """Drives tile reveal and wipe animations on a Minimap."""

    def __init__(self, minimap: "Minimap"):
        self.minimap = minimap

    @staticmethod
    def items_per_tick(total_items: int, duration_ms: int, tick_ms: int) -> int:
        """How many items to process each tick so total_items finish in duration_ms."""
        num_ticks = max(1, duration_ms // tick_ms)
        return max(1, math.ceil(total_items / num_ticks))

    def advance_growing(self) -> bool:
        """Expand or shrink registered tiles by one frame. Returns True if any remain."""
        m = self.minimap
        still = []
        for entry in m._growing:
            age = entry["age"] + 1
            entry["age"] = age

            if entry["shrinking"]:
                t = max(0.0, 1.0 - age / m._grow_frames)
            else:
                t = min(1.0, age / m._grow_frames)

            half = entry["half"] * t
            cx, cy = entry["cx"], entry["cy"]
            try:
                m.canvas.coords(
                    entry["id"], cx - half, cy - half, cx + half, cy + half
                )
            except Exception:
                continue

            if entry["shrinking"]:
                if age < m._grow_frames:
                    still.append(entry)
                else:
                    try:
                        m.canvas.delete(entry["id"])
                    except Exception:
                        pass
            else:
                if age < m._grow_frames:
                    still.append(entry)

        m._growing = still
        return bool(still)

    def start_reveal(self) -> None:
        """Animate tiles in diagonal order (new / different level)."""
        m = self.minimap
        layout = m._compute_layout()
        if layout is None:
            m._layout = None
            return

        m._layout = layout
        m._has_drawn_content = True
        m._tiles_complete = False
        m._growing = []

        m.tile_draw.draw_goal_marker(layout)
        m.tile_draw.draw_start_marker(layout)

        num_diags = layout["max_diag"] + 1
        m._diags_per_tick = self.items_per_tick(
            num_diags, m._tile_reveal_ms, m._tick_ms
        )
        m._tile_next_d = 0
        m._tiles_done = False

        m._on_reveal_started(layout)
        m._schedule_tick()

    def advance_tile_reveal(self, layout: dict[str, Any]) -> None:
        m = self.minimap
        max_diag = layout["max_diag"]
        next_d = m._tile_next_d

        if next_d <= max_diag:
            end_d = min(next_d + m._diags_per_tick - 1, max_diag)
            for d in range(next_d, end_d + 1):
                m.tile_draw.draw_diagonal(layout, d, grow=True)
            m._tile_next_d = end_d + 1

        still_growing = self.advance_growing()
        if m._tile_next_d > max_diag and not still_growing:
            m._tiles_done = True
            m._tiles_complete = True

    def start_wipe(self) -> None:
        m = self.minimap
        layout = m._layout
        if layout is None:
            self.finish_wipe()
            return

        m.canvas.delete("path")
        m.canvas.delete("marker")
        m._growing = []
        m._tiles_done = False
        m._path_done = True
        m._tiles_complete = False

        max_diag = layout["max_diag"]
        diags_per_tick = self.items_per_tick(
            max_diag + 1, m._tile_wipe_ms, m._tick_ms
        )
        gen = m._anim_gen
        self.wipe_step(max_diag, diags_per_tick, gen)

    def queue_diag_shrink(self, layout: dict[str, Any], d: int) -> None:
        """Register tiles on diagonal d for shrink-out (reuse canvas items)."""
        m = self.minimap
        for item_id in m.canvas.find_withtag(f"diag_{d}"):
            tags = m.canvas.gettags(item_id)
            if "tile" not in tags:
                continue
            coords = m.canvas.coords(item_id)
            if len(coords) < 4:
                continue
            x1, y1, x2, y2 = coords[:4]
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            half = layout["scale"] / 2
            m._growing.append(
                {
                    "id": item_id,
                    "cx": cx,
                    "cy": cy,
                    "half": half,
                    "age": 0,
                    "shrinking": True,
                }
            )

    def wipe_step(self, next_d: int, diags_per_tick: int, gen: int) -> None:
        m = self.minimap
        if gen != m._anim_gen:
            return

        layout = m._layout
        if layout is None:
            self.finish_wipe()
            return

        end_d = max(next_d - diags_per_tick + 1, 0)
        for d in range(next_d, end_d - 1, -1):
            self.queue_diag_shrink(layout, d)

        still_growing = self.advance_growing()
        wiped_all = end_d <= 0

        if gen != m._anim_gen:
            return

        if not wiped_all or still_growing:
            m._anim_after_id = m.after(
                m._tick_ms,
                lambda: self.wipe_step(
                    end_d - 1 if not wiped_all else -1,
                    diags_per_tick,
                    gen,
                ),
            )
        else:
            self.finish_wipe()

    def finish_wipe(self) -> None:
        m = self.minimap
        m._anim_after_id = None
        m.canvas.delete("all")
        m._clear_state()
        m._has_drawn_content = False
        m._tiles_complete = False
