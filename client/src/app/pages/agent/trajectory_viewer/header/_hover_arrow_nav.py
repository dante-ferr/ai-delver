from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .header import TrajectoryHeader


class HoverArrowNav:
    """Arrow-key run/grid navigation while the pointer hovers grid or scrub."""

    def __init__(self, header: "TrajectoryHeader"):
        self.header = header

    def install(self):
        try:
            top = self.header.winfo_toplevel()
            top.bind("<KeyPress-Left>", self.on_arrow_left, add="+")
            top.bind("<KeyPress-Right>", self.on_arrow_right, add="+")
            top.bind("<Shift-KeyPress-Left>", self.on_shift_arrow_left, add="+")
            top.bind("<Shift-KeyPress-Right>", self.on_shift_arrow_right, add="+")
            top.bind("<Shift-Left>", self.on_shift_arrow_left, add="+")
            top.bind("<Shift-Right>", self.on_shift_arrow_right, add="+")
            top.bind("<KeyPress-Up>", self.on_arrow_up, add="+")
            top.bind("<KeyPress-Down>", self.on_arrow_down, add="+")
        except Exception:
            pass
        self.bind_nav_hover(self.header.run_grid.canvas_frame)
        self.bind_nav_hover(self.header.scrub_row)
        canvas = self.header.run_grid.canvas
        try:
            # Widget-level binds + "break" beat the Canvas class yview bindings
            # that otherwise steal Up/Down once the grid is click-focused.
            canvas.bind("<KeyPress-Left>", self.on_arrow_left, add="+")
            canvas.bind("<KeyPress-Right>", self.on_arrow_right, add="+")
            canvas.bind("<Shift-KeyPress-Left>", self.on_shift_arrow_left, add="+")
            canvas.bind("<Shift-KeyPress-Right>", self.on_shift_arrow_right, add="+")
            canvas.bind("<Shift-Left>", self.on_shift_arrow_left, add="+")
            canvas.bind("<Shift-Right>", self.on_shift_arrow_right, add="+")
            canvas.bind("<KeyPress-Up>", self.on_arrow_up, add="+")
            canvas.bind("<KeyPress-Down>", self.on_arrow_down, add="+")
        except Exception:
            pass

    def bind_nav_hover(self, widget):
        def on_enter(_event):
            if self.focus_blocks_arrow_nav():
                return
            try:
                self.header.run_grid.canvas.focus_set()
            except Exception:
                pass

        def on_leave(_event):
            self.header.after_idle(self.sync_nav_focus)

        try:
            widget.bind("<Enter>", on_enter, add="+")
            widget.bind("<Leave>", on_leave, add="+")
        except Exception:
            return
        try:
            for child in widget.winfo_children():
                self.bind_nav_hover(child)
        except Exception:
            pass

    def sync_nav_focus(self):
        """Drop canvas focus once the pointer leaves grid/scrub nav zones."""
        if self.pointer_over_nav_zones():
            return
        try:
            focus = self.header.focus_get()
        except Exception:
            return
        canvas = self.header.run_grid.canvas
        if focus is canvas:
            try:
                self.header.winfo_toplevel().focus_set()
            except Exception:
                try:
                    self.header.focus_set()
                except Exception:
                    pass

    def pointer_over_nav_zones(self) -> bool:
        try:
            x, y = self.header.winfo_pointerxy()
        except Exception:
            return False
        zones = []
        try:
            zones.append(self.header.run_grid.canvas_frame)
        except Exception:
            pass
        zones.append(self.header.scrub_row)
        for zone in zones:
            try:
                if not zone.winfo_ismapped():
                    continue
                wx = int(zone.winfo_rootx())
                wy = int(zone.winfo_rooty())
                ww = int(zone.winfo_width())
                wh = int(zone.winfo_height())
            except Exception:
                continue
            if wx <= x < wx + ww and wy <= y < wy + wh:
                return True
        return False

    def focus_blocks_arrow_nav(self) -> bool:
        """Don't steal arrows from text entries."""
        try:
            focus = self.header.focus_get()
        except Exception:
            return False
        if focus is None:
            return False
        widget = focus
        while widget is not None:
            try:
                if widget == self.header.index_entry:
                    return True
                cls = widget.winfo_class()
            except Exception:
                break
            if cls in ("Entry", "Text", "TEntry", "TCombobox"):
                return True
            try:
                widget = widget.master
            except Exception:
                break
        return False

    def _nav_allowed(self) -> bool:
        try:
            if not self.header.winfo_exists():
                return False
        except Exception:
            return False
        if self.focus_blocks_arrow_nav() or not self.pointer_over_nav_zones():
            return False
        return True

    def on_arrow_left(self, event=None):
        if not self._nav_allowed():
            return
        if event is not None and getattr(event, "state", 0) & 1:
            self.header._on_prev_landmark()
        else:
            self.header._on_prev_run()
        return "break"

    def on_arrow_right(self, event=None):
        if not self._nav_allowed():
            return
        if event is not None and getattr(event, "state", 0) & 1:
            self.header._on_next_landmark()
        else:
            self.header._on_next_run()
        return "break"

    def on_shift_arrow_left(self, _event=None):
        if not self._nav_allowed():
            return
        self.header._on_prev_landmark()
        return "break"

    def on_shift_arrow_right(self, _event=None):
        if not self._nav_allowed():
            return
        self.header._on_next_landmark()
        return "break"

    def on_arrow_up(self, _event):
        if not self._nav_allowed():
            return
        self.header.run_grid.interaction.nudge_selection_row(-1)
        return "break"

    def on_arrow_down(self, _event):
        if not self._nav_allowed():
            return
        self.header.run_grid.interaction.nudge_selection_row(1)
        return "break"
