"""Filterable scrollable level list for the playtest browser."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from ._level_catalog import LevelEntry

_SELECTED_FG = ("#d0d4dc", "#2a2226")
_IDLE_FG = "transparent"


class LevelListPanel(ctk.CTkFrame):
    """Searchable list of level entries; notifies owner on selection."""

    def __init__(
        self,
        master,
        *,
        on_select: Callable[[LevelEntry], None],
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        from app.fonts import app_font
        from src.app.components import MouseWheelScrollableFrame
        from src.config import config

        self._on_select = on_select
        self._entries: list[LevelEntry] = []
        self._selected: LevelEntry | None = None
        self._row_widgets: dict[str, ctk.CTkFrame] = {}
        self._app_font = app_font
        self._font_size = config.STYLE.FONT.STANDARD_SIZE
        self._subtitle_size = config.STYLE.FONT.SUBTITLE_SIZE

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            self,
            text="Levels",
            anchor="w",
            font=app_font(size=self._subtitle_size, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", pady=(0, 6))

        self._filter = ctk.CTkEntry(
            self,
            placeholder_text="Filter levels…",
            font=app_font(size=self._font_size),
        )
        self._filter.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self._filter.bind("<KeyRelease>", lambda _e: self._rebuild_list())

        self._list = MouseWheelScrollableFrame(self, fg_color="transparent")
        self._list.grid(row=2, column=0, sticky="nsew")

        self._empty = ctk.CTkLabel(
            self._list,
            text="No levels found under handcrafted/ or generated/.",
            font=app_font(size=self._font_size),
            text_color="#a69ea1",
        )

    def set_entries(self, entries: list[LevelEntry]) -> None:
        self._entries = list(entries)
        self._rebuild_list()

    def selected(self) -> LevelEntry | None:
        return self._selected

    def _rebuild_list(self) -> None:
        """Full rebuild — only for filter changes / catalog refresh."""
        for child in self._list.winfo_children():
            child.destroy()
        self._row_widgets.clear()

        query = self._filter.get().strip().lower()
        visible = [
            e
            for e in self._entries
            if not query
            or query in e.display_label.lower()
            or query in e.name.lower()
            or query in e.source.lower()
        ]

        if not visible:
            self._empty.configure(
                text=(
                    "No matching levels."
                    if self._entries
                    else "No levels found under handcrafted/ or generated/."
                )
            )
            self._empty.pack(anchor="w", padx=4, pady=8)
            return

        for entry in visible:
            self._add_row(entry)

    def _add_row(self, entry: LevelEntry) -> None:
        selected = (
            self._selected is not None and self._selected.play_ref == entry.play_ref
        )
        row = ctk.CTkFrame(
            self._list,
            fg_color=_SELECTED_FG if selected else _IDLE_FG,
            corner_radius=6,
            cursor="hand2",
        )
        row.pack(fill="x", padx=2, pady=2)

        source_color = "#6BBF6B" if entry.source == "handcrafted" else "#E8A05A"
        badge = ctk.CTkLabel(
            row,
            text=entry.source[:4],
            width=42,
            anchor="center",
            font=self._app_font(size=10, weight="bold"),
            text_color=source_color,
        )
        badge.pack(side="left", padx=(8, 4), pady=8)

        label = ctk.CTkLabel(
            row,
            text=entry.display_label,
            anchor="w",
            font=self._app_font(size=self._font_size),
        )
        label.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=8)

        def _select(_event=None, e=entry):
            self._select_entry(e)

        for widget in (row, badge, label):
            widget.bind("<Button-1>", _select)
            self._list.bind_scroll_events_recursively(widget)

        self._row_widgets[entry.play_ref] = row

    def _select_entry(self, entry: LevelEntry) -> None:
        prev = self._selected
        if prev is not None and prev.play_ref == entry.play_ref:
            return

        self._selected = entry
        if prev is not None:
            self._set_row_highlight(prev.play_ref, False)
        self._set_row_highlight(entry.play_ref, True)
        self._on_select(entry)

    def _set_row_highlight(self, play_ref: str, selected: bool) -> None:
        row = self._row_widgets.get(play_ref)
        if row is not None and row.winfo_exists():
            row.configure(fg_color=_SELECTED_FG if selected else _IDLE_FG)
