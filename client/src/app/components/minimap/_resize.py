"""Debounced canvas resize handling for the minimap."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .minimap import Minimap


class MinimapResize:
    """Debounces Configure events and triggers a sync redraw."""

    def __init__(self, minimap: "Minimap"):
        self.minimap = minimap

    def on_configure(self, _event=None) -> None:
        m = self.minimap
        if m._configure_after_id is not None:
            try:
                m.after_cancel(m._configure_after_id)
            except Exception:
                pass
        m._configure_after_id = m.after(m._debounce_ms, self.on_configure_debounced)

    def on_configure_debounced(self) -> None:
        m = self.minimap
        m._configure_after_id = None
        if m._waiting_for_canvas:
            m._try_start_pending_reveal()
            return
        # Ignore size changes mid-animation so we don't snap/grow after it ends.
        if m._is_animating():
            return
        m.draw_minimap()

    def cancel(self) -> None:
        m = self.minimap
        if m._configure_after_id is not None:
            try:
                m.after_cancel(m._configure_after_id)
            except Exception:
                pass
            m._configure_after_id = None
