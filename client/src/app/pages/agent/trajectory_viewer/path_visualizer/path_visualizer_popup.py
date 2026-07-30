"""Resizable popup that shows only the path visualizer."""

from __future__ import annotations

import customtkinter as ctk

from ..run_grid._config import _cfg
from .trajectory_minimap import TrajectoryMinimap


class PathVisualizerPopup(ctk.CTkToplevel):
    """Expanded path visualizer — intentionally a separate window the user can resize."""

    def __init__(self, master, viewer):
        from app_manager import app_manager

        parent = getattr(app_manager, "editor_app", None) or master
        super().__init__(parent)

        self.withdraw()
        self.transient(parent)
        try:
            self.attributes("-type", "dialog")
        except Exception:
            pass

        self.title("Path Visualizer")
        self._viewer = viewer
        self._popup_w = int(_cfg("PATH_POPUP_WIDTH", 720))
        self._popup_h = int(_cfg("PATH_POPUP_HEIGHT", 560))
        self.geometry(f"{self._popup_w}x{self._popup_h}")
        self.minsize(420, 320)
        self.resizable(True, True)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.minimap = TrajectoryMinimap(self)
        self.minimap.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.after(10, self._reveal)

    def _center_on_screen(self) -> None:
        """Place the popup at the center of the screen / parent window."""
        if not self.winfo_exists():
            return
        self.update_idletasks()
        w = self.winfo_width() if self.winfo_width() > 1 else self.winfo_reqwidth()
        h = self.winfo_height() if self.winfo_height() > 1 else self.winfo_reqheight()
        parent = self.master
        try:
            if parent is not None:
                parent.update_idletasks()
                # Prefer the parent window's monitor area (multi-monitor safe).
                px = int(parent.winfo_rootx())
                py = int(parent.winfo_rooty())
                pw = int(parent.winfo_width())
                ph = int(parent.winfo_height())
                x = px + max(0, (pw - w) // 2)
                y = py + max(0, (ph - h) // 2)
            else:
                sw = int(self.winfo_screenwidth())
                sh = int(self.winfo_screenheight())
                x = max(0, (sw - w) // 2)
                y = max(0, (sh - h) // 2)
        except Exception:
            x, y = 80, 80
        try:
            # Tell the WM the app chose the position (don't snap to cursor).
            self.wm_positionfrom("user")
        except Exception:
            pass
        self.geometry(f"+{x}+{y}")

    def _reveal(self):
        self._center_on_screen()
        self.deiconify()
        self.lift()
        self.focus_set()
        # Tiling WMs (notably Hyprland) often place type=dialog windows at the
        # cursor on map, ignoring pre-map geometry — re-assert after mapping.
        self.after_idle(self._center_on_screen)
        self.after(50, self._center_on_screen)

    def sync(
        self,
        trajectory,
        grid_size,
        tile_size,
        walls,
        start_pos,
        goal_pos,
        *,
        animate: bool = False,
    ):
        if trajectory is None:
            self.minimap.reset_to_default()
            return
        self.minimap.update_minimap(
            trajectory,
            grid_size,
            tile_size,
            walls,
            start_pos,
            goal_pos,
            animate=animate,
        )
