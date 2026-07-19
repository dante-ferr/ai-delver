from __future__ import annotations

from datetime import datetime
from typing import Any

import customtkinter as ctk

from app.components.mouse_whell_scrollable_frame.mouse_wheel_scrollable_frame import (
    MouseWheelScrollableFrame,
)
from app.components.overlay import Overlay
from app.components.overlay.message_overlay import MessageOverlay
from src.config import config


class CheckpointRestoreOverlay(Overlay):
    """Filterable table of checkpoints for restoring the current agent's weights."""

    COLUMNS = ("Level", "Date", "Cycle", "Kind")
    COL_WEIGHTS = (3, 3, 1, 2)

    def __init__(self, agent_name: str, checkpoints: list[dict[str, Any]]):
        from app.components import StandardButton

        super().__init__("restore_checkpoint")

        self.agent_name = agent_name
        self._all_checkpoints = list(checkpoints)
        self._selected_id: str | None = None
        self._rows: dict[str, ctk.CTkFrame] = {}

        title = ctk.CTkLabel(
            self,
            text=f"Restore checkpoint for “{agent_name}”",
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
            anchor="w",
        )
        title.pack(padx=12, pady=(12, 4), fill="x")

        filters = ctk.CTkFrame(self, fg_color="transparent")
        filters.pack(padx=12, pady=(0, 8), fill="x")
        filters.grid_columnconfigure(0, weight=2)
        filters.grid_columnconfigure(1, weight=1)

        self._filter_var = ctk.StringVar()
        self._filter_var.trace_add("write", self._on_filters_changed)
        self.filter_entry = ctk.CTkEntry(
            filters,
            textvariable=self._filter_var,
            placeholder_text="Filter by level, kind, id…",
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        self.filter_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        levels = sorted(
            {
                str(entry.get("level") or "unknown")
                for entry in self._all_checkpoints
            },
            key=str.lower,
        )
        self._level_var = ctk.StringVar(value="All levels")
        self.level_menu = ctk.CTkOptionMenu(
            filters,
            variable=self._level_var,
            values=["All levels", *levels],
            command=lambda _v: self._on_filters_changed(),
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        self.level_menu.grid(row=0, column=1, sticky="ew")

        header = ctk.CTkFrame(self, fg_color=("gray80", "gray20"), corner_radius=4)
        header.pack(padx=12, pady=(0, 4), fill="x")
        for i, (label, weight) in enumerate(zip(self.COLUMNS, self.COL_WEIGHTS)):
            header.grid_columnconfigure(i, weight=weight, uniform="ckpt")
            ctk.CTkLabel(
                header,
                text=label,
                anchor="w",
                font=ctk.CTkFont(
                    size=config.STYLE.FONT.STANDARD_SIZE,
                    weight="bold",
                ),
            ).grid(row=0, column=i, sticky="ew", padx=8, pady=6)

        self.list_frame = MouseWheelScrollableFrame(
            self,
            height=280,
            fg_color="transparent",
        )
        self.list_frame.pack(padx=12, pady=(0, 8), fill="both", expand=True)

        self._empty_label = ctk.CTkLabel(
            self.list_frame,
            text="No matching checkpoints.",
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        )

        for entry in self._all_checkpoints:
            self._create_row(entry)

        if self._all_checkpoints:
            self._select(self._all_checkpoints[0]["id"])
        self._on_filters_changed()

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(padx=12, pady=(0, 12), fill="x")

        StandardButton(
            actions,
            text="Cancel",
            command=self._close,
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        ).pack(side="right", padx=(8, 0))

        StandardButton(
            actions,
            text="Restore",
            command=self._on_restore,
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        ).pack(side="right")

        self.filter_entry.bind("<Return>", lambda _e: self._on_restore())
        self.filter_entry.bind("<Escape>", lambda _e: self._close())
        self.bind("<Return>", lambda _e: self._on_restore())
        self.bind("<Escape>", lambda _e: self._close())

        self._post_init_config()
        self.after(50, self.filter_entry.focus_set)

    def _post_init_config(self):
        self.minsize(width=640, height=480)
        self.maxsize(width=720, height=560)
        self.resizable(False, False)
        self.center()

    @staticmethod
    def _format_date(value: Any) -> str:
        if not value:
            return "—"
        text = str(value)
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return text

    @staticmethod
    def _format_cycle(value: Any) -> str:
        if value is None:
            return "—"
        return str(value)

    @staticmethod
    def _format_kind(value: Any) -> str:
        kind = str(value or "unknown")
        return kind.replace("_", " ")

    def _create_row(self, entry: dict[str, Any]) -> ctk.CTkFrame:
        entry_id = entry["id"]
        row = ctk.CTkFrame(
            self.list_frame,
            fg_color="transparent",
            corner_radius=4,
            cursor="hand2",
        )
        values = (
            str(entry.get("level") or "unknown"),
            self._format_date(entry.get("created_at")),
            self._format_cycle(entry.get("cycle")),
            self._format_kind(entry.get("kind")),
        )
        for i, (text, weight) in enumerate(zip(values, self.COL_WEIGHTS)):
            row.grid_columnconfigure(i, weight=weight, uniform="ckpt")
            label = ctk.CTkLabel(
                row,
                text=text,
                anchor="w",
                font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
            )
            label.grid(row=0, column=i, sticky="ew", padx=8, pady=4)

            def on_select(_event=None, selected=entry_id):
                self._select(selected)

            def on_activate(_event=None, selected=entry_id):
                self._select(selected)
                self._on_restore()

            label.bind("<Button-1>", on_select)
            label.bind("<Double-Button-1>", on_activate)

        def on_select_row(_event=None, selected=entry_id):
            self._select(selected)

        def on_activate_row(_event=None, selected=entry_id):
            self._select(selected)
            self._on_restore()

        row.bind("<Button-1>", on_select_row)
        row.bind("<Double-Button-1>", on_activate_row)
        self.list_frame.bind_scroll_events_recursively(row)
        row.pack(fill="x", pady=1)
        self._rows[entry_id] = row
        return row

    def _select(self, entry_id: str):
        previous = self._rows.get(self._selected_id) if self._selected_id else None
        if previous is not None:
            previous.configure(fg_color="transparent")

        self._selected_id = entry_id
        row = self._rows.get(entry_id)
        if row is not None:
            row.configure(fg_color=("gray75", "gray25"))

    def _matches_filters(self, entry: dict[str, Any]) -> bool:
        level_filter = self._level_var.get()
        if level_filter != "All levels" and str(entry.get("level") or "unknown") != level_filter:
            return False

        query = self._filter_var.get().strip().lower()
        if not query:
            return True

        haystack = " ".join(
            [
                str(entry.get("level") or ""),
                str(entry.get("kind") or ""),
                str(entry.get("id") or ""),
                str(entry.get("cycle") if entry.get("cycle") is not None else ""),
                self._format_date(entry.get("created_at")),
            ]
        ).lower()
        return query in haystack

    def _on_filters_changed(self, *_args):
        visible: list[str] = []
        for entry in self._all_checkpoints:
            entry_id = entry["id"]
            row = self._rows[entry_id]
            if self._matches_filters(entry):
                row.pack(fill="x", pady=1)
                visible.append(entry_id)
            else:
                row.pack_forget()

        if visible:
            self._empty_label.pack_forget()
            if self._selected_id not in visible:
                self._select(visible[0])
        else:
            self._empty_label.pack(pady=8)
            self._selected_id = None

        self.list_frame.after(10, self.list_frame._check_scroll_visibility)

    def _selected_entry(self) -> dict[str, Any] | None:
        if not self._selected_id:
            return None
        for entry in self._all_checkpoints:
            if entry["id"] == self._selected_id:
                return entry
        return None

    def _on_restore(self):
        entry = self._selected_entry()
        if entry is None:
            return
        if not self._matches_filters(entry):
            return

        selected_id = entry["id"]
        level = entry.get("level") or "unknown"
        kind = self._format_kind(entry.get("kind"))
        date = self._format_date(entry.get("created_at"))
        self._close()
        MessageOverlay(
            f'Restore Delver weights to checkpoint for level "{level}" '
            f"({kind}, {date})? This replaces the current model weights.",
            subject="Warning",
            button_commands={
                "Yes": lambda: self._restore(selected_id, level),
                "No (cancel)": lambda: None,
            },
        )

    def _restore(self, checkpoint_id: str, level: str):
        from cli.commands.checkpoint_store import restore_checkpoint

        try:
            restore_checkpoint(self.agent_name, checkpoint_id)
        except Exception as e:
            MessageOverlay(f"Failed to restore checkpoint: {e}", subject="Error")
            return

        MessageOverlay(
            f'Successfully restored weights from checkpoint for level "{level}".',
            subject="Success",
        )
