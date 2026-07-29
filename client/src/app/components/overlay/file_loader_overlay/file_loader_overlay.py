from app.theme import theme
from app.components.overlay.message_overlay import MessageOverlay
from app.fonts import app_font
from app.components.overlay import Overlay
from app.components.mouse_whell_scrollable_frame.mouse_wheel_scrollable_frame import (
    MouseWheelScrollableFrame,
)
import customtkinter as ctk
from pathlib import Path
from src.config import config


class FileLoaderOverlay(Overlay):
    """Modal picker with filter-as-you-type and a scrollable name list."""

    def __init__(
        self,
        file_dirs: dict[str, Path],
        file_type: str,
        show_sucess_message: bool = True,
    ):
        from app.components import StandardButton

        super().__init__("file_loader")

        self.file_dirs = file_dirs
        self.file_type = file_type
        self.show_sucess_message = show_sucess_message

        self._sorted_names = sorted(file_dirs.keys(), key=str.lower)
        self._selected_name = self._sorted_names[0]
        self._rows: dict[str, ctk.CTkFrame] = {}

        label = ctk.CTkLabel(
            self,
            text=self._prompt_text(),
            wraplength=320,
            font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        label.pack(padx=12, pady=(12, 4), anchor="w", fill="x")

        self._filter_var = ctk.StringVar()
        self._filter_var.trace_add("write", self._on_filter)

        self.filter_entry = ctk.CTkEntry(
            self,
            textvariable=self._filter_var,
            placeholder_text="Filter…",
            font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        self.filter_entry.pack(padx=12, pady=(0, 8), fill="x")
        self.filter_entry.bind("<Return>", lambda _e: self._on_action())
        self.filter_entry.bind("<Escape>", lambda _e: self._close())

        self.list_frame = MouseWheelScrollableFrame(
            self,
            height=260,
            fg_color="transparent",
        )
        self.list_frame.pack(padx=12, pady=(0, 8), fill="both", expand=True)

        self._empty_label = ctk.CTkLabel(
            self.list_frame,
            text="No matches.",
            font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
        )

        for name in self._sorted_names:
            self._create_row(name)

        self._select(self._selected_name)

        action_button = StandardButton(
            self,
            text=self._action_button_text(),
            command=self._on_action,
            font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        action_button.pack(padx=12, pady=(0, 12), anchor="e")

        self.bind("<Return>", lambda _e: self._on_action())
        self.bind("<Escape>", lambda _e: self._close())

        self._post_init_config()
        self.after(50, self.filter_entry.focus_set)

    def _prompt_text(self) -> str:
        return f"Choose a {self.file_type} file to load."

    def _action_button_text(self) -> str:
        return "Load"

    def _on_action(self):
        self._load()

    def _post_init_config(self):
        self.minsize(width=360, height=420)
        self.maxsize(width=360, height=420)
        self.resizable(False, False)
        self._reveal()

    def _create_row(self, name: str) -> ctk.CTkFrame:
        row = ctk.CTkFrame(
            self.list_frame,
            fg_color="transparent",
            corner_radius=4,
            cursor="hand2",
        )
        label = ctk.CTkLabel(
            row,
            text=name,
            anchor="w",
            font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        label.pack(fill="x", padx=8, pady=4)

        def on_select(_event=None, selected=name):
            self._select(selected)

        def on_activate(_event=None, selected=name):
            self._select(selected)
            self._on_action()

        for widget in (row, label):
            widget.bind("<Button-1>", on_select)
            widget.bind("<Double-Button-1>", on_activate)

        self.list_frame.bind_scroll_events_recursively(row)
        row.pack(fill="x", pady=1)
        self._rows[name] = row
        return row

    def _select(self, name: str):
        previous = self._rows.get(self._selected_name)
        if previous is not None:
            previous.configure(fg_color="transparent")

        self._selected_name = name
        row = self._rows.get(name)
        if row is not None:
            row.configure(fg_color=("gray75", theme.secondary_dark))

    def _on_filter(self, *_args):
        query = self._filter_var.get().strip().lower()
        visible: list[str] = []

        for name, row in self._rows.items():
            if query in name.lower():
                row.pack(fill="x", pady=1)
                visible.append(name)
            else:
                row.pack_forget()

        if visible:
            self._empty_label.pack_forget()
            if self._selected_name not in visible:
                self._select(visible[0])
        else:
            self._empty_label.pack(pady=8)

        self.list_frame.after(10, self.list_frame._check_scroll_visibility)

    def get_selected_name(self) -> str:
        return self._selected_name

    def _get_file_path(self) -> Path:
        """Returns the path of the selected file. Must be called in the _load method."""
        return self.file_dirs[self._selected_name]

    def _load(self):
        if not self._rows:
            return
        # Re-check filter: selected may be hidden if the list was emptied.
        query = self._filter_var.get().strip().lower()
        if query and query not in self._selected_name.lower():
            return

        self._close()
        if self.show_sucess_message:
            MessageOverlay(
                f"Sucessfully loaded the {self.file_type}.", subject="Success"
            )
