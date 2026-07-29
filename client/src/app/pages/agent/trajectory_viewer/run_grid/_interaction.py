from __future__ import annotations

import customtkinter as ctk

from app.fonts import app_font
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .run_grid import RunGrid

class RunGridInteraction:
    def __init__(self, grid: "RunGrid"):
        self.grid = grid

    def emit_select(self, index: int):
        g = self.grid
        old_focus = g._focused_level_hash
        g._selected_index = index
        scrolled = g.renderer.ensure_index_visible(index)
        entry = g.data.entry(index)
        new_focus = None
        if entry:
            new_focus = str(entry.get("level_hash", "") or "") or None
        g._focused_level_hash = new_focus
        if scrolled:
            g.renderer.redraw()
        else:
            g.renderer.move_selection_ring(index)
        if old_focus != new_focus:
            touched = {h for h in (old_focus, new_focus) if h}
            g.legend.refresh_legend_styles(hashes=touched or None)
            if new_focus:
                g.legend.scroll_legend_to(new_focus)
        if g.on_select:
            g.on_select(index)

    def ensure_tooltip_widget(self):
        """In-window overlay — avoids a separate Hyprland / WM client."""
        g = self.grid
        if g._tooltip is not None and g._tooltip.winfo_exists():
            return
        g._tooltip = ctk.CTkFrame(
            g,
            fg_color="#111827",
            corner_radius=4,
            border_width=1,
            border_color="#374151",
        )
        g._tooltip_label = ctk.CTkLabel(
            g._tooltip,
            text="",
            font=app_font(size=11),
            text_color="#f9fafb",
            justify="left",
            anchor="nw",
        )
        g._tooltip_label.pack(padx=8, pady=6)

    def hide_tooltip(self):
        g = self.grid
        if g._tooltip_after_id is not None:
            try:
                g.after_cancel(g._tooltip_after_id)
            except Exception:
                pass
            g._tooltip_after_id = None
        if g._tooltip is not None and g._tooltip.winfo_exists():
            g._tooltip.place_forget()

    def on_click(self, event):
        g = self.grid
        g.canvas.focus_set()
        index = g.renderer.index_at_xy(event.x, event.y)
        if index is not None:
            g.interaction.emit_select(index)

    def on_double_click(self, event):
        g = self.grid
        index = g.renderer.index_at_xy(event.x, event.y)
        if index is not None:
            g.interaction.emit_select(index)
            if g.on_replay:
                g.on_replay(index)

    def on_leave(self, _event=None):
        g = self.grid
        g._hover_index = None
        g.interaction.hide_tooltip()

    def nudge_selection_row(self, direction: int) -> None:
        """Move selection by one grid row (Up/Down)."""
        g = self.grid
        if not g._visible_indices:
            return
        cols = max(1, g.renderer.compute_cols())
        current = g._selected_index
        slot = g.renderer.slot_for_index(current) if current is not None else 0
        if slot is None:
            slot = 0
        slot = max(0, min(len(g._visible_indices) - 1, slot + int(direction) * cols))
        g.interaction.emit_select(g._visible_indices[slot])

    def on_key(self, event):
        g = self.grid
        if not g._visible_indices:
            return
        # Only while pointer is over grid/scrub — avoid sticky keys after leave.
        header = g.master
        hover_nav = getattr(header, "hover_nav", None)
        if hover_nav is not None and not hover_nav.pointer_over_nav_zones():
            return
        key = event.keysym
        cols = g.renderer.compute_cols()
        current = g._selected_index
        slot = g.renderer.slot_for_index(current) if current is not None else 0
        if slot is None:
            slot = 0

        # Arrow keys are handled by HoverArrowNav (with "break" so Canvas
        # class bindings cannot yview-scroll the focused grid).
        if key == "l":
            slot = min(len(g._visible_indices) - 1, slot + 1)
        elif key == "h":
            slot = max(0, slot - 1)
        elif key == "j":
            slot = min(len(g._visible_indices) - 1, slot + cols)
        elif key == "k":
            slot = max(0, slot - cols)
        elif key == "Home":
            slot = 0
        elif key == "End":
            slot = len(g._visible_indices) - 1
        elif key == "Prior":
            slot = max(0, slot - cols * g.visible_rows)
        elif key == "Next":
            slot = min(
                len(g._visible_indices) - 1, slot + cols * g.visible_rows
            )
        elif key in ("Return", "space"):
            if current is not None and g.on_replay:
                g.on_replay(current)
            return "break"
        else:
            return

        g.interaction.emit_select(g._visible_indices[slot])
        return "break"

    def on_motion(self, event):
        g = self.grid
        index = g.renderer.index_at_xy(event.x, event.y)
        if index == g._hover_index:
            if index is not None and g._tooltip is not None:
                g.interaction.place_tooltip(event.x_root, event.y_root)
            return
        g._hover_index = index
        g.interaction.hide_tooltip()
        if index is None:
            return
        if g._tooltip_after_id is not None:
            try:
                g.after_cancel(g._tooltip_after_id)
            except Exception:
                pass
        x_root, y_root = event.x_root, event.y_root
        g._tooltip_after_id = g.after(
            g.tooltip_delay_ms,
            lambda: g.interaction.show_tooltip(index, x_root, y_root),
        )

    def on_mouse_wheel(self, event):
        g = self.grid
        total_rows = g.renderer.total_rows()
        view_rows = max(1, int(g.canvas.winfo_height()) // g.row_height)
        if total_rows <= view_rows:
            return
        if event.num == 5 or (getattr(event, "delta", 0) < 0):
            delta = 1
        elif event.num == 4 or (getattr(event, "delta", 0) > 0):
            delta = -1
        else:
            return
        g._scroll_row = max(0, min(total_rows - view_rows, g._scroll_row + delta))
        g.renderer.redraw()

    def on_scrollbar(self, *args):
        g = self.grid
        total_rows = g.renderer.total_rows()
        view_rows = max(1, int(g.canvas.winfo_height()) // g.row_height)
        max_row = max(0, total_rows - view_rows)
        if not args:
            return
        op = args[0]
        if op == "moveto":
            frac = float(args[1])
            g._scroll_row = int(frac * max_row)
        elif op == "scroll":
            amount = int(args[1])
            unit = args[2] if len(args) > 2 else "units"
            step = view_rows if unit == "pages" else 1
            g._scroll_row = max(0, min(max_row, g._scroll_row + amount * step))
        g.renderer.redraw()

    def place_tooltip(self, x_root: int, y_root: int):
        g = self.grid
        if g._tooltip is None or not g._tooltip.winfo_exists():
            return
        # Convert screen coords → RunGrid-local, then clamp inside the widget.
        local_x = x_root - g.winfo_rootx() + 14
        local_y = y_root - g.winfo_rooty() + 14
        g._tooltip.update_idletasks()
        tip_w = max(1, g._tooltip.winfo_reqwidth())
        tip_h = max(1, g._tooltip.winfo_reqheight())
        max_x = max(0, g.winfo_width() - tip_w - 4)
        max_y = max(0, g.winfo_height() - tip_h - 4)
        local_x = max(0, min(local_x, max_x))
        local_y = max(0, min(local_y, max_y))
        g._tooltip.place(x=local_x, y=local_y)
        g._tooltip.lift()

    def show_tooltip(self, index: int, x_root: int, y_root: int):
        g = self.grid
        g._tooltip_after_id = None
        if g._hover_index != index:
            return
        g.data.ensure_visible_entries([index])
        entry = g.data.entry(index)
        if entry is None:
            return
        level_hash = str(entry.get("level_hash", "") or "")
        name = g.data.train_name_for_hash(level_hash)
        outcome = "Win" if entry.get("victorious") else "Loss"
        kind = str(entry.get("kind") or "train")
        reward = entry.get("total_reward")
        reward_str = f"{reward:.4f}" if isinstance(reward, (int, float)) else "N/A"
        steps = entry.get("steps")
        aps = entry.get("actions_per_second")
        if isinstance(steps, int) and isinstance(aps, int) and aps > 0:
            dur = f"{steps / aps:.2f}s ({steps} frames)"
        elif isinstance(steps, int):
            dur = f"{steps} frames"
        else:
            dur = "N/A"
        conf = entry.get("policy_confidence")
        conf_str = f"{conf:.3f}" if isinstance(conf, (int, float)) else "N/A"
        takeoffs = entry.get("jump_takeoffs")
        takeoffs_str = str(takeoffs) if takeoffs is not None else "N/A"
        cycle = entry.get("cycle")
        cycle_str = str(cycle) if cycle is not None else "—"

        text = (
            f"Run {index + 1}\n"
            f"{outcome} · {kind}\n"
            f"{g.data.truncate_hash(level_hash)} · {name}\n"
            f"Reward {reward_str} · {dur}\n"
            f"Confidence {conf_str} · Takeoffs {takeoffs_str}\n"
            f"Cycle {cycle_str}"
        )
        g.interaction.ensure_tooltip_widget()
        if g._tooltip_label is not None:
            g._tooltip_label.configure(text=text)
        g.interaction.place_tooltip(x_root, y_root)

    def start_pulse(self):
        g = self.grid
        def tick():
            g._pulse_on = not g._pulse_on
            try:
                mapped = bool(g.winfo_ismapped())
            except Exception:
                mapped = False
            if mapped and g._live_mode and g._selected_index is not None:
                g.renderer.update_selection_ring()
            g._pulse_after_id = g.after(g.live_pulse_ms, tick)

        g._pulse_after_id = g.after(g.live_pulse_ms, tick)
