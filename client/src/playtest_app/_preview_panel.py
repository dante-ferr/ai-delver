"""Minimap preview + Play button for the selected level."""

from __future__ import annotations

import json
from collections.abc import Callable

import customtkinter as ctk

from ._level_catalog import LevelEntry


class PreviewPanel(ctk.CTkFrame):
    """Shows minimap + metadata for the selected level and a Play action."""

    def __init__(
        self,
        master,
        *,
        on_play: Callable[[LevelEntry], None],
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        from app.fonts import app_font
        from src.app.components import Minimap
        from src.config import config

        self._on_play = on_play
        self._entry: LevelEntry | None = None
        self._app_font = app_font
        self._font_size = config.STYLE.FONT.STANDARD_SIZE
        self._subtitle_size = config.STYLE.FONT.SUBTITLE_SIZE

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        header.grid_columnconfigure(0, weight=1)

        self._title = ctk.CTkLabel(
            header,
            text="Select a level",
            anchor="w",
            font=app_font(size=self._subtitle_size, weight="bold"),
        )
        self._title.grid(row=0, column=0, sticky="ew")

        self._meta = ctk.CTkLabel(
            header,
            text="Choose a level from the list to preview its layout.",
            anchor="w",
            font=app_font(size=11),
            text_color="#888888",
        )
        self._meta.grid(row=1, column=0, sticky="ew", pady=(2, 0))

        self.minimap = Minimap(self)
        self.minimap.grid(row=1, column=0, sticky="nsew", pady=(0, 12))

        self._play = ctk.CTkButton(
            self,
            text="Play level",
            font=app_font(size=self._font_size, weight="bold"),
            command=self._handle_play,
            state="disabled",
            height=36,
        )
        self._play.grid(row=2, column=0, sticky="ew")

        self._hint = ctk.CTkLabel(
            self,
            text="Controls in play window: Left / Right to run, Space to jump.",
            anchor="w",
            font=app_font(size=11),
            text_color="#888888",
        )
        self._hint.grid(row=3, column=0, sticky="ew", pady=(8, 0))

    def show_entry(self, entry: LevelEntry) -> None:
        from src.app.utils.level_minimap_geometry import parse_level_minimap_geometry

        self._entry = entry
        self._title.configure(text=entry.name)
        self._meta.configure(text=f"{entry.source} · {entry.display_label}")
        self._play.configure(state="normal")

        try:
            data = json.loads(entry.level_json.read_text(encoding="utf-8"))
            geom = parse_level_minimap_geometry(data)
            self.minimap.set_level(
                geom.grid_size,
                geom.tile_size,
                geom.walls,
                geom.start_pos,
                geom.goal_pos,
                level_hash=entry.play_ref,
                animate=False,
            )
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            self.minimap.reset_to_default()
            self._meta.configure(text=f"Failed to load preview: {exc}")
            self._play.configure(state="disabled")

    def clear(self) -> None:
        self._entry = None
        self._title.configure(text="Select a level")
        self._meta.configure(text="Choose a level from the list to preview its layout.")
        self._play.configure(state="disabled")
        self.minimap.reset_to_default()

    def _handle_play(self) -> None:
        if self._entry is not None:
            self._on_play(self._entry)
