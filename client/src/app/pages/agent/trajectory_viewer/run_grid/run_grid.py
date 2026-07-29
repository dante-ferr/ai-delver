"""Scrollable, virtually drawn run-picker grid for the trajectory viewer."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import customtkinter as ctk

from app.components import MouseWheelScrollableFrame
from app.fonts import app_font
from app.theme import theme

from ._config import _cfg, resolve_bg_color
from ._data import RunGridData
from ._interaction import RunGridInteraction
from ._legend import RunGridLegend
from ._navigation import RunGridNavigation
from ._renderer import RunGridRenderer


class RunGrid(ctk.CTkFrame):
    """
    Dense run matrix: color = level, filled = win / hollow = loss,
    gold border = play kind. Virtual scroll + overscan for large N.
    """

    def __init__(
        self,
        master,
        *,
        on_select: Callable[[int], None] | None = None,
        on_replay: Callable[[int], None] | None = None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_select = on_select
        self.on_replay = on_replay

        self.cell_size = int(_cfg("CELL_SIZE", 14))
        self.cell_gap = int(_cfg("CELL_GAP", 2))
        self.row_height = int(_cfg("ROW_HEIGHT", 16))
        self.visible_rows = int(_cfg("VISIBLE_ROWS", 6))
        self.overscan_rows = int(_cfg("OVERSCAN_ROWS", 2))
        self.max_height = int(_cfg("MAX_HEIGHT", 120))
        self.legend_hash_chars = int(_cfg("LEGEND_HASH_CHARS", 12))
        self.legend_width = int(_cfg("LEGEND_WIDTH", 180))
        self.legend_name_max_chars = int(_cfg("LEGEND_NAME_MAX_CHARS", 18))
        self.legend_name_hover_ms = int(_cfg("LEGEND_NAME_HOVER_MS", 1200))
        self.side_by_side_min_width = int(_cfg("SIDE_BY_SIDE_MIN_WIDTH", 520))
        self.tooltip_delay_ms = int(_cfg("TOOLTIP_DELAY_MS", 80))
        self.live_pulse_ms = int(_cfg("LIVE_PULSE_MS", 450))
        self.play_border_color = str(_cfg("PLAY_BORDER_COLOR", "#fbbf24"))
        self.selection_color = str(_cfg("SELECTION_COLOR", "#ffffff"))
        self.live_color = str(_cfg("LIVE_COLOR", "#60a5fa"))

        self._run_index: list[dict | None] = []
        self._level_archive: dict = {}
        self._level_hashes: dict = {}
        self._trajectory_dir: Path | None = None
        self._metadata: dict = {}
        self._visible_indices: list[int] = []
        self._selected_index: int | None = None
        self._live_mode = False
        self._wins_only = False
        self._hide_play = False
        self._level_filters: set[str] = set()
        self._focused_level_hash: str | None = None
        self._legend_rows: dict[str, dict] = {}
        self._cols = 1
        self._scroll_row = 0
        self._pulse_on = False
        self._pulse_after_id = None
        self._tooltip: ctk.CTkFrame | None = None
        self._tooltip_label: ctk.CTkLabel | None = None
        self._tooltip_after_id = None
        self._hover_index: int | None = None
        self._backfill_busy = False
        self._side_by_side: bool | None = None
        self._available_width = 320
        self._ordered_level_hashes: list[str] = []
        self._copy_hash_overlay: ctk.CTkFrame | None = None
        self._copy_hash_after_id = None
        self._copy_hash_hide_after_id = None
        self._context_hash: str = ""
        self._copy_dismiss_bound = False
        self._canvas_redraw_after_id = None
        self._name_hover_overlay: ctk.CTkFrame | None = None
        self._name_hover_label: ctk.CTkLabel | None = None
        self._hover_legend_hash: str | None = None
        self._name_hover_after_id = None
        self._name_hover_pos: tuple[int, int] | None = None

        # Legend row style tokens
        self._STYLE_FILTER = {
            "fg_color": theme.primary_color,
            "text_color": "#000000",
        }
        self._STYLE_FOCUS = {
            "fg_color": theme.secondary_dark,
            "text_color": theme.primary_color,
        }
        self._STYLE_IDLE = {
            "fg_color": "transparent",
            "text_color": theme.text_light,
        }

        self.grid_columnconfigure(0, weight=1)

        self.data = RunGridData(self)
        self.navigation = RunGridNavigation(self)
        self.renderer = RunGridRenderer(self)
        self.legend = RunGridLegend(self)
        self.interaction = RunGridInteraction(self)

        # Filters / jumps
        self.controls = ctk.CTkFrame(self, fg_color="transparent")
        self.controls.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        self.wins_var = ctk.BooleanVar(value=False)
        self.hide_play_var = ctk.BooleanVar(value=False)

        self.wins_cb = ctk.CTkCheckBox(
            self.controls,
            text="Wins only",
            variable=self.wins_var,
            command=self.data.on_filters_changed,
            checkbox_width=18,
            checkbox_height=18,
            font=app_font(size=11),
            width=90,
        )
        self.wins_cb.pack(side="left", padx=(0, 8))

        self.hide_play_cb = ctk.CTkCheckBox(
            self.controls,
            text="Hide play",
            variable=self.hide_play_var,
            command=self.data.on_filters_changed,
            checkbox_width=18,
            checkbox_height=18,
            font=app_font(size=11),
            width=90,
        )
        self.hide_play_cb.pack(side="left", padx=(0, 8))

        self.first_win_btn = ctk.CTkButton(
            self.controls,
            text="First win",
            width=72,
            height=22,
            font=app_font(size=11),
            command=self.jump_first_win,
        )
        self.first_win_btn.pack(side="left", padx=(4, 4))

        self.last_win_btn = ctk.CTkButton(
            self.controls,
            text="Last win",
            width=72,
            height=22,
            font=app_font(size=11),
            command=self.jump_last_win,
        )
        self.last_win_btn.pack(side="left", padx=(0, 4))

        self.clear_filter_btn = ctk.CTkButton(
            self.controls,
            text="Clear level filter",
            font=app_font(size=11),
            height=22,
            command=self.clear_level_filter,
            state="disabled",
        )
        self.clear_filter_btn.pack(side="left", padx=(8, 0))

        # Body: grid + legend (side-by-side when wide)
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew")
        self.grid_rowconfigure(1, weight=1)

        self.canvas_frame = ctk.CTkFrame(self.body, fg_color=theme.bg_darkest, corner_radius=6)
        self.canvas_frame.grid_columnconfigure(0, weight=1)
        self.canvas_frame.grid_rowconfigure(0, weight=1)

        self._panel_height = min(self.max_height, self.visible_rows * self.row_height + 8)
        self.canvas = ctk.CTkCanvas(
            self.canvas_frame,
            height=self._panel_height,
            bg=resolve_bg_color(self.canvas_frame, theme.bg_darkest),
            highlightthickness=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)

        self.scrollbar = ctk.CTkScrollbar(
            self.canvas_frame,
            orientation="vertical",
            command=self.interaction.on_scrollbar,
            width=12,
        )
        self.scrollbar.grid(row=0, column=1, sticky="ns", padx=(2, 4), pady=4)

        self.legend_column = ctk.CTkFrame(self.body, fg_color="transparent")
        self.legend_column.grid_columnconfigure(0, weight=1)
        self.legend_column.grid_rowconfigure(1, weight=1)

        self.legend_title = ctk.CTkLabel(
            self.legend_column,
            text="Levels (hash · train name)",
            font=app_font(size=11, weight="bold"),
            text_color=theme.primary_color,
            anchor="w",
        )
        self.legend_title.grid(row=0, column=0, sticky="ew", pady=(0, 2))

        self.legend_scroll = MouseWheelScrollableFrame(
            self.legend_column,
            height=self._panel_height,
            fg_color=theme.bg_dark,
            corner_radius=6,
        )
        self.legend_scroll.grid(row=1, column=0, sticky="nsew")

        self.canvas.bind("<Configure>", self.renderer.on_canvas_configure)
        self.canvas.bind("<Button-1>", self.interaction.on_click)
        self.canvas.bind("<Double-Button-1>", self.interaction.on_double_click)
        self.canvas.bind("<Motion>", self.interaction.on_motion)
        self.canvas.bind("<Leave>", self.interaction.on_leave)
        self.canvas.bind("<MouseWheel>", self.interaction.on_mouse_wheel)
        self.canvas.bind("<Button-4>", self.interaction.on_mouse_wheel)
        self.canvas.bind("<Button-5>", self.interaction.on_mouse_wheel)
        self.canvas.bind("<KeyPress>", self.interaction.on_key)
        self.canvas.bind("<FocusIn>", lambda _e: None)
        self.canvas.configure(takefocus=1)

        self._apply_body_layout(side_by_side=False)
        self.interaction.start_pulse()

    # ------------------------------------------------------------------ public


    def set_width(self, width: int):
        """Decide side-by-side vs stacked. Does not force canvas pixel width
        (that was feeding a Configure resize loop / panel shake)."""
        width = max(160, int(width))
        if abs(width - self._available_width) < 4 and self._side_by_side is not None:
            side_by_side = width >= self.side_by_side_min_width
            if side_by_side == self._side_by_side:
                return
        self._available_width = width
        self._apply_body_layout(side_by_side=width >= self.side_by_side_min_width)
        try:
            self.legend_scroll.configure(height=self._panel_height)
        except Exception:
            pass


    def _apply_body_layout(self, *, side_by_side: bool):
        if side_by_side == self._side_by_side:
            return
        self._side_by_side = side_by_side

        for col in range(2):
            self.body.grid_columnconfigure(col, weight=0, minsize=0)
        for row in range(2):
            self.body.grid_rowconfigure(row, weight=0, minsize=0)

        self.canvas_frame.grid_forget()
        self.legend_column.grid_forget()

        if side_by_side:
            # Grid takes remaining space; legend stays narrow (names-only).
            self.body.grid_columnconfigure(0, weight=1)
            self.body.grid_columnconfigure(1, weight=0, minsize=self.legend_width)
            self.body.grid_rowconfigure(0, weight=1)
            self.canvas_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
            self.legend_column.grid(row=0, column=1, sticky="nsew")
            self.legend_title.configure(
                text="Levels — shift multi-filter · hover for full name"
            )
        else:
            self.body.grid_columnconfigure(0, weight=1)
            self.body.grid_rowconfigure(0, weight=0)
            self.body.grid_rowconfigure(1, weight=0)
            self.canvas_frame.grid(row=0, column=0, sticky="ew")
            self.legend_column.grid(row=1, column=0, sticky="ew", pady=(6, 0))
            self.legend_title.configure(
                text="Levels — click/shift filter · hover name · right-click hash"
            )


    def set_live_mode(self, enabled: bool):
        enabled = bool(enabled)
        if self._live_mode == enabled:
            return
        self._live_mode = enabled
        # Recolor the existing ring — avoid wiping the whole grid.
        if self.canvas.find_withtag("selection_ring"):
            self.renderer.update_selection_ring()
        else:
            self.renderer.move_selection_ring(self._selected_index)


    def set_selected_index(self, index: int | None):
        old_focus = self._focused_level_hash
        same_index = index == self._selected_index
        self._selected_index = index
        new_focus = None
        scrolled = False
        if index is not None:
            if not same_index:
                scrolled = self.renderer.ensure_index_visible(index)
            entry = self.data.entry(index)
            if entry:
                new_focus = str(entry.get("level_hash", "") or "") or None
        self._focused_level_hash = new_focus
        if not same_index:
            if scrolled:
                self.renderer.redraw()
            else:
                self.renderer.move_selection_ring(index)
        if old_focus != new_focus:
            touched = {h for h in (old_focus, new_focus) if h}
            self.legend.refresh_legend_styles(hashes=touched or None)
            if new_focus:
                self.legend.scroll_legend_to(new_focus)


    def refresh_from_disk(self):
        self.data.refresh_from_disk()

    def train_name_for_hash(self, level_hash: str) -> str:
        return self.data.train_name_for_hash(level_hash)

    def truncate_hash(self, digest: str) -> str:
        return self.data.truncate_hash(digest)

    def jump_first_win(self):
        self.navigation.jump_first_win()

    def jump_last_win(self):
        self.navigation.jump_last_win()

    def clear_level_filter(self):
        self.navigation.clear_level_filter()

    def jump_prev_level(self):
        self.navigation.jump_prev_level()

    def jump_next_level(self):
        self.navigation.jump_next_level()

    def jump_prev_run(self):
        self.navigation.jump_prev_run()

    def jump_next_run(self):
        self.navigation.jump_next_run()

    def jump_prev_landmark(self):
        self.navigation.jump_prev_landmark()

    def jump_next_landmark(self):
        self.navigation.jump_next_landmark()

