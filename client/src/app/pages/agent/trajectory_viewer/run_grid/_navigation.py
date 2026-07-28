from __future__ import annotations

import customtkinter as ctk

from app.fonts import app_font, canvas_font
from typing import TYPE_CHECKING

from ._config import color_for_level_hash

if TYPE_CHECKING:
    from .run_grid import RunGrid

class RunGridNavigation:
    def __init__(self, grid: "RunGrid"):
        self.grid = grid

    def adjacent_level_index(self, *, direction: int) -> int | None:
        g = self.grid
        if not g._run_index:
            return None
        start = g._selected_index
        if start is None:
            start = 0 if direction > 0 else len(g._run_index) - 1

        current = g.data.entry(start)
        current_hash = (
            str(current.get("level_hash", "") or "") if current else ""
        )

        if direction > 0:
            i = start + 1
            while i < len(g._run_index):
                entry = g.data.entry(i)
                if not entry:
                    i += 1
                    continue
                h = str(entry.get("level_hash", "") or "")
                if h != current_hash:
                    return i
                i += 1
            return None

        # Walk back out of the current block, then to the start of the previous.
        i = start - 1
        while i >= 0:
            entry = g.data.entry(i)
            if not entry:
                i -= 1
                continue
            h = str(entry.get("level_hash", "") or "")
            if h != current_hash:
                target_hash = h
                while i > 0:
                    prev = g.data.entry(i - 1)
                    if not prev or str(prev.get("level_hash", "") or "") != target_hash:
                        break
                    i -= 1
                return i
            i -= 1
        return None

    # ----------------------------------------------------------------- filters

    def find_win(self, level_hash: str | None, *, last: bool) -> int | None:
        g = self.grid
        indices = range(len(g._run_index))
        if last:
            indices = range(len(g._run_index) - 1, -1, -1)
        for i in indices:
            entry = g.data.entry(i)
            if not entry or not entry.get("victorious"):
                continue
            if level_hash is not None and entry.get("level_hash") != level_hash:
                continue
            if g._hide_play and entry.get("kind") == "play":
                continue
            return i
        return None

    # ---------------------------------------------------------------- geometry

    def level_landmarks(self) -> list[int]:
        g = self.grid
        """Ordered [begin, end, begin, end, …] for contiguous level blocks."""
        landmarks: list[int] = []
        i = 0
        n = len(g._run_index)
        while i < n:
            entry = g.data.entry(i)
            if not entry:
                i += 1
                continue
            level_hash = str(entry.get("level_hash", "") or "")
            begin = i
            while i + 1 < n:
                nxt = g.data.entry(i + 1)
                if not nxt or str(nxt.get("level_hash", "") or "") != level_hash:
                    break
                i += 1
            end = i
            landmarks.append(begin)
            if end != begin:
                landmarks.append(end)
            i += 1
        return landmarks

    def primary_level_hash(self) -> str | None:
        g = self.grid
        if g._focused_level_hash and (
            not g._level_filters or g._focused_level_hash in g._level_filters
        ):
            return g._focused_level_hash
        if g._level_filters:
            return next(iter(g._level_filters))
        return g._focused_level_hash

    def clear_level_filter(self):
        g = self.grid
        if not g._level_filters:
            g.clear_filter_btn.configure(state="disabled")
            return
        touched = set(g._level_filters)
        g._level_filters.clear()
        g.clear_filter_btn.configure(state="disabled")
        g.data.rebuild_visible()
        g.renderer.redraw()
        g.legend.refresh_legend_styles(hashes=touched)

    def jump_first_win(self):
        g = self.grid
        target_hash = g.navigation.primary_level_hash()
        idx = g.navigation.find_win(target_hash, last=False)
        if idx is not None:
            g.interaction.emit_select(idx)

    def jump_last_win(self):
        g = self.grid
        target_hash = g.navigation.primary_level_hash()
        idx = g.navigation.find_win(target_hash, last=True)
        if idx is not None:
            g.interaction.emit_select(idx)

    def jump_next_landmark(self):
        g = self.grid
        """Walk level landmarks forward: begin → end → next begin → next end → …"""
        landmarks = g.navigation.level_landmarks()
        if not landmarks:
            return
        cur = g._selected_index if g._selected_index is not None else -1
        for lm in landmarks:
            if lm > cur:
                g.interaction.emit_select(lm)
                return

    def jump_next_level(self):
        g = self.grid
        """Jump to the first run of the next level block."""
        idx = g.navigation.adjacent_level_index(direction=1)
        if idx is not None:
            g.interaction.emit_select(idx)

    def jump_next_run(self):
        g = self.grid
        if not g._run_index:
            return
        cur = g._selected_index if g._selected_index is not None else -1
        if cur + 1 < len(g._run_index):
            g.interaction.emit_select(cur + 1)

    def jump_prev_landmark(self):
        g = self.grid
        """Walk level landmarks backward: … → next begin → end → begin."""
        landmarks = g.navigation.level_landmarks()
        if not landmarks:
            return
        cur = g._selected_index if g._selected_index is not None else landmarks[-1] + 1
        for lm in reversed(landmarks):
            if lm < cur:
                g.interaction.emit_select(lm)
                return

    def jump_prev_level(self):
        g = self.grid
        """Jump to the first run of the previous level block."""
        idx = g.navigation.adjacent_level_index(direction=-1)
        if idx is not None:
            g.interaction.emit_select(idx)

    def jump_prev_run(self):
        g = self.grid
        if not g._run_index:
            return
        cur = g._selected_index if g._selected_index is not None else 0
        if cur > 0:
            g.interaction.emit_select(cur - 1)
