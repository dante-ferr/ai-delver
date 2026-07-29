from __future__ import annotations

import customtkinter as ctk

from app.fonts import app_font, canvas_font
from app.theme import theme
from typing import TYPE_CHECKING

from ._config import color_for_level_hash

if TYPE_CHECKING:
    from .run_grid import RunGrid

class RunGridLegend:
    def __init__(self, grid: "RunGrid"):
        self.grid = grid

    def cancel_copy_hash_hide(self):
        g = self.grid
        if g._copy_hash_hide_after_id is not None:
            try:
                g.after_cancel(g._copy_hash_hide_after_id)
            except Exception:
                pass
            g._copy_hash_hide_after_id = None

    def cancel_legend_name_overlay(self):
        g = self.grid
        if g._name_hover_after_id is not None:
            try:
                g.after_cancel(g._name_hover_after_id)
            except Exception:
                pass
            g._name_hover_after_id = None

    def copy_context_hash(self):
        g = self.grid
        digest = g._context_hash
        g.legend.hide_copy_hash_overlay()
        if not digest:
            return
        try:
            g.clipboard_clear()
            g.clipboard_append(digest)
        except Exception:
            return
        note = ctk.CTkLabel(
            g,
            text="Hash copied",
            font=app_font(size=11),
            fg_color="#065f46",
            text_color="#ecfdf5",
            corner_radius=4,
        )
        note.place(relx=0.5, rely=0.08, anchor="n")
        g.after(1200, note.destroy)

    # --------------------------------------------------------------- interaction

    def dismiss_copy_on_click(self, _event=None):
        g = self.grid
        g.legend.hide_copy_hash_overlay()

    def ensure_legend_name_overlay(self):
        g = self.grid
        if g._name_hover_overlay is not None and g._name_hover_overlay.winfo_exists():
            return
        g._name_hover_overlay = ctk.CTkFrame(
            g,
            fg_color=theme.bg_dark,
            corner_radius=4,
            border_width=1,
            border_color=theme.bg_mid,
        )
        g._name_hover_label = ctk.CTkLabel(
            g._name_hover_overlay,
            text="",
            font=app_font(size=11),
            text_color=theme.text_light,
            justify="left",
            anchor="w",
        )
        g._name_hover_label.pack(padx=8, pady=4)

    def fire_legend_name_overlay(self, level_hash: str):
        g = self.grid
        g._name_hover_after_id = None
        if g._hover_legend_hash != level_hash:
            return
        pos = g._name_hover_pos or (0, 0)
        g.legend.show_legend_name_overlay(level_hash, pos[0], pos[1])

    def hide_copy_hash_overlay(self):
        g = self.grid
        g.legend.cancel_copy_hash_hide()
        if g._copy_hash_after_id is not None:
            try:
                g.after_cancel(g._copy_hash_after_id)
            except Exception:
                pass
            g._copy_hash_after_id = None
        if g._copy_hash_overlay is not None:
            try:
                g._copy_hash_overlay.destroy()
            except Exception:
                pass
            g._copy_hash_overlay = None
        g._context_hash = ""

    def hide_legend_name_overlay(self):
        g = self.grid
        if g._name_hover_overlay is not None and g._name_hover_overlay.winfo_exists():
            g._name_hover_overlay.place_forget()

    def legend_style_for(self, level_hash: str) -> dict:
        g = self.grid
        if level_hash in g._level_filters:
            return g._STYLE_FILTER
        if level_hash == g._focused_level_hash:
            return g._STYLE_FOCUS
        return g._STYLE_IDLE

    def on_legend_enter(self, event, level_hash: str):
        g = self.grid
        g._hover_legend_hash = level_hash
        g._name_hover_pos = (event.x_root, event.y_root)
        g.legend.schedule_legend_name_overlay(level_hash)

    def on_legend_leave(self, _event, level_hash: str):
        g = self.grid
        if g._hover_legend_hash == level_hash:
            g._hover_legend_hash = None
            g.legend.cancel_legend_name_overlay()
            g.legend.hide_legend_name_overlay()
        if g._context_hash == level_hash:
            # Short delay so the pointer can move onto the Copy hash button.
            g.legend.schedule_copy_hash_hide()

    def on_legend_left_click(self, event, level_hash: str):
        g = self.grid
        shift = bool(event.state & 0x0001)
        touched = set(g._level_filters)
        touched.add(level_hash)

        if shift:
            if level_hash in g._level_filters:
                g._level_filters.discard(level_hash)
            else:
                g._level_filters.add(level_hash)
        else:
            if level_hash in g._level_filters:
                # Normal-click an already-filtered level → clear all.
                g._level_filters.clear()
            else:
                # Normal-click a new level → sole filter.
                g._level_filters = {level_hash}

        g.clear_filter_btn.configure(
            state="normal" if g._level_filters else "disabled"
        )
        g.data.rebuild_visible()
        g.renderer.redraw()
        g.legend.refresh_legend_styles(hashes=touched | set(g._level_filters))

    def on_legend_motion(self, event, level_hash: str):
        g = self.grid
        if g._hover_legend_hash != level_hash:
            g._hover_legend_hash = level_hash
            g.legend.schedule_legend_name_overlay(level_hash)
        g._name_hover_pos = (event.x_root, event.y_root)
        # If already visible, keep it following the pointer.
        if (
            g._name_hover_overlay is not None
            and g._name_hover_overlay.winfo_ismapped()
        ):
            g.legend.place_legend_name_overlay(event.x_root, event.y_root)

    def on_legend_right_click(self, event, level_hash: str):
        g = self.grid
        g._context_hash = level_hash
        g.legend.hide_copy_hash_overlay()

        overlay = ctk.CTkFrame(
            g,
            fg_color=theme.bg_dark,
            corner_radius=6,
            border_width=1,
            border_color=theme.bg_mid,
        )
        btn = ctk.CTkButton(
            overlay,
            text="Copy hash",
            width=100,
            height=26,
            font=app_font(size=11),
            command=g.legend.copy_context_hash,
        )
        btn.pack(padx=6, pady=6)

        local_x = event.x_root - g.winfo_rootx()
        local_y = event.y_root - g.winfo_rooty()
        overlay.update_idletasks()
        tip_w = max(1, overlay.winfo_reqwidth())
        tip_h = max(1, overlay.winfo_reqheight())
        max_x = max(0, g.winfo_width() - tip_w - 4)
        max_y = max(0, g.winfo_height() - tip_h - 4)
        overlay.place(x=max(0, min(local_x, max_x)), y=max(0, min(local_y, max_y)))
        overlay.lift()
        g._copy_hash_overlay = overlay
        overlay.bind("<Enter>", lambda _e: g.legend.cancel_copy_hash_hide())
        overlay.bind("<Leave>", lambda _e: g.legend.schedule_copy_hash_hide())
        btn.bind("<Enter>", lambda _e: g.legend.cancel_copy_hash_hide())

        g._copy_hash_after_id = g.after(4000, g.legend.hide_copy_hash_overlay)
        if not g._copy_dismiss_bound:
            g.bind("<Button-1>", g.legend.dismiss_copy_on_click, add="+")
            g._copy_dismiss_bound = True

    def place_legend_name_overlay(self, x_root: int, y_root: int):
        g = self.grid
        if g._name_hover_overlay is None or not g._name_hover_overlay.winfo_exists():
            return
        local_x = x_root - g.winfo_rootx() + 12
        local_y = y_root - g.winfo_rooty() + 14
        g._name_hover_overlay.update_idletasks()
        tip_w = max(1, g._name_hover_overlay.winfo_reqwidth())
        tip_h = max(1, g._name_hover_overlay.winfo_reqheight())
        max_x = max(0, g.winfo_width() - tip_w - 4)
        max_y = max(0, g.winfo_height() - tip_h - 4)
        g._name_hover_overlay.place(
            x=max(0, min(local_x, max_x)),
            y=max(0, min(local_y, max_y)),
        )
        g._name_hover_overlay.lift()

    def rebuild_legend(self):
        g = self.grid
        """Rebuild legend structure only when the set/order of levels changes."""
        seen: dict[str, str] = {}
        ordered: list[str] = []
        for entry in g._run_index:
            if not isinstance(entry, dict):
                continue
            h = str(entry.get("level_hash", "") or "")
            if not h or h in seen:
                continue
            seen[h] = g.data.train_name_for_hash(h)
            ordered.append(h)

        if ordered == g._ordered_level_hashes and g._legend_rows:
            # Same levels — refresh names/styles in place (no destroy flash).
            for h, name in seen.items():
                info = g._legend_rows.get(h)
                if not info:
                    continue
                display = g.legend.truncate_legend_name(name)
                if info["label"].cget("text") != display:
                    info["label"].configure(text=display)
                info["name"] = name
            g.legend.refresh_legend_styles()
            return

        g._ordered_level_hashes = ordered
        for child in g.legend_scroll.winfo_children():
            child.destroy()
        g._legend_rows.clear()

        if not seen:
            empty = ctk.CTkLabel(
                g.legend_scroll,
                text="No levels yet",
                font=app_font(size=11),
                text_color="#6b7280",
            )
            empty.pack(anchor="w", padx=6, pady=4)
            g.legend_scroll.bind_scroll_events_recursively(empty)
            return

        for level_hash in ordered:
            name = seen[level_hash]
            color = color_for_level_hash(level_hash, ordered_hashes=ordered)
            row = ctk.CTkFrame(g.legend_scroll, fg_color="transparent", corner_radius=4)
            row.pack(fill="x", padx=4, pady=1)

            swatch = ctk.CTkCanvas(
                row, width=12, height=12, highlightthickness=0, bg=theme.bg_darkest
            )
            swatch.pack(side="left", padx=(2, 6), pady=2)
            swatch.create_rectangle(1, 1, 11, 11, fill=color, outline=color)

            # Label (not Button) avoids CTk press-animation flash on click.
            display_name = g.legend.truncate_legend_name(name)
            label = ctk.CTkLabel(
                row,
                text=display_name,
                anchor="w",
                height=22,
                fg_color="transparent",
                text_color=theme.text_light,
                font=app_font(size=11),
                cursor="hand2",
            )
            label.pack(side="left", fill="x", expand=True, padx=(0, 4), pady=1)

            def bind_clicks(widget, h=level_hash):
                widget.bind(
                    "<Button-1>",
                    lambda e, hh=h: g.legend.on_legend_left_click(e, hh),
                )
                widget.bind(
                    "<Button-3>",
                    lambda e, hh=h: g.legend.on_legend_right_click(e, hh),
                )
                widget.bind(
                    "<Enter>",
                    lambda e, hh=h: g.legend.on_legend_enter(e, hh),
                )
                widget.bind(
                    "<Leave>",
                    lambda e, hh=h: g.legend.on_legend_leave(e, hh),
                )
                widget.bind(
                    "<Motion>",
                    lambda e, hh=h: g.legend.on_legend_motion(e, hh),
                )

            bind_clicks(row)
            bind_clicks(label)
            bind_clicks(swatch)

            g._legend_rows[level_hash] = {
                "row": row,
                "label": label,
                "swatch": swatch,
                "name": name,
            }
            g.legend_scroll.bind_scroll_events_recursively(row)

        g.legend.refresh_legend_styles()
        try:
            g.legend_scroll.configure(height=g._panel_height)
            g.after(0, g.legend_scroll._check_scroll_visibility)
        except Exception:
            pass

    def refresh_legend_styles(self, hashes: set[str] | None = None):
        g = self.grid
        targets = hashes if hashes is not None else set(g._legend_rows)
        for level_hash in targets:
            info = g._legend_rows.get(level_hash)
            if not info:
                continue
            style = g.legend.legend_style_for(level_hash)
            try:
                # Colors only — do not retune font weight/size (that was shrinking labels).
                info["row"].configure(fg_color=style["fg_color"])
                info["label"].configure(
                    fg_color="transparent",
                    text_color=style["text_color"],
                )
            except Exception:
                pass

    def schedule_copy_hash_hide(self):
        g = self.grid
        g.legend.cancel_copy_hash_hide()
        g._copy_hash_hide_after_id = g.after(120, g.legend.hide_copy_hash_overlay)

    def schedule_legend_name_overlay(self, level_hash: str):
        g = self.grid
        g.legend.cancel_legend_name_overlay()
        g.legend.hide_legend_name_overlay()
        delay = max(0, int(g.legend_name_hover_ms))
        g._name_hover_after_id = g.after(
            delay, lambda: g.legend.fire_legend_name_overlay(level_hash)
        )

    def scroll_legend_to(self, level_hash: str):
        g = self.grid
        info = g._legend_rows.get(level_hash)
        if not info:
            return
        row = info["row"]
        try:
            g.legend_scroll.update_idletasks()
            canvas = g.legend_scroll._parent_canvas
            y = row.winfo_y()
            inner_h = max(1, g.legend_scroll.winfo_reqheight())
            view_h = max(1, canvas.winfo_height())
            if inner_h <= view_h:
                return
            target = max(0.0, (y - view_h * 0.3) / max(1, inner_h - view_h))
            canvas.yview_moveto(min(1.0, target))
        except Exception:
            pass

    def show_legend_name_overlay(self, level_hash: str, x_root: int, y_root: int):
        g = self.grid
        info = g._legend_rows.get(level_hash)
        if not info:
            return
        full_name = str(info.get("name") or "")
        if not full_name:
            return
        g.legend.ensure_legend_name_overlay()
        if g._name_hover_label is not None:
            g._name_hover_label.configure(text=full_name)
        g.legend.place_legend_name_overlay(x_root, y_root)

    def truncate_legend_name(self, name: str) -> str:
        g = self.grid
        n = max(4, int(g.legend_name_max_chars))
        if len(name) <= n:
            return name
        return name[: max(1, n - 1)] + "…"
