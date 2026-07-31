"""Standalone CustomTkinter app: browse levels, preview minimap, launch playtest."""

from __future__ import annotations

import customtkinter as ctk

from level import LevelLoader

from ._level_catalog import LevelEntry, list_playable_levels
from ._level_list_panel import LevelListPanel
from ._play_session import PlaySession
from ._preview_panel import PreviewPanel


def run_playtest_app() -> None:
    """Initialize theme/fonts and run the playtest browser main loop."""
    # Theme/font setup pulls editor deps; keep it inside the launcher only.
    from app.ctk_cursor_patch import apply_ctk_cursor_patch
    from app.fonts import init_fonts
    from app.theme import theme

    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme(str(theme.path))
    apply_ctk_cursor_patch()
    init_fonts()

    app = PlaytestApp()
    app.mainloop()


class PlaytestApp(ctk.CTk):
    """Secondary dev app for selecting, previewing, and playing levels."""

    def __init__(self):
        super().__init__()
        from app.fonts import app_font
        from src.config import config

        gui = config.PLAYTEST_GUI
        self._gui = gui
        self.title(str(gui.TITLE))
        width = int(gui.WINDOW_WIDTH)
        height = int(gui.WINDOW_HEIGHT)
        self.geometry(f"{width}x{height}")
        self.minsize(720, 480)

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(16, 8))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text=str(gui.TITLE),
            anchor="w",
            font=app_font(size=20, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        self._status = ctk.CTkLabel(
            header,
            text="",
            anchor="e",
            font=app_font(size=11),
            text_color="#888888",
        )
        self._status.grid(row=0, column=1, sticky="e")

        regen = ctk.CTkButton(
            header,
            text=str(gui.REGEN_PACK_BUTTON_LABEL),
            width=140,
            command=self._regen_pack,
            font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        regen.grid(row=0, column=2, padx=(12, 0))

        refresh = ctk.CTkButton(
            header,
            text="Refresh",
            width=90,
            command=self.refresh_levels,
            font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        refresh.grid(row=0, column=3, padx=(8, 0))

        self._list = LevelListPanel(self, on_select=self._on_level_selected)
        self._list.grid(row=1, column=0, sticky="nsew", padx=(20, 8), pady=(0, 20))

        self._preview = PreviewPanel(self, on_play=self._on_play)
        self._preview.grid(row=1, column=1, sticky="nsew", padx=(8, 20), pady=(0, 20))

        self._play_session = PlaySession(self, on_stopped=self._on_play_stopped)
        self._catalog_status = ""
        self._regen_busy = False
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.refresh_levels()

    def refresh_levels(self) -> None:
        entries = list_playable_levels()
        self._list.set_entries(entries)
        handcrafted = sum(1 for e in entries if e.source == "handcrafted")
        generated = sum(1 for e in entries if e.source == "generated")
        self._catalog_status = (
            f"{len(entries)} levels · {handcrafted} handcrafted · {generated} generated"
        )
        self._status.configure(text=self._catalog_status)
        if not entries:
            self._preview.clear()

    def _regen_pack(self) -> None:
        if self._regen_busy:
            return
        if self._play_session.active:
            self._status.configure(text="Close the play window before regenerating.")
            return

        from level.procedural.pack import generate_platforming_pack
        from utils.level_groups import load_level_groups, save_level_groups

        group = str(self._gui.REGEN_PACK_GROUP)
        count = int(self._gui.REGEN_PACK_COUNT)
        self._regen_busy = True
        self._status.configure(text=f"Regenerating @{group} ({count} levels)…")
        self.update_idletasks()

        def _register(group_name: str, level_names: list[str]) -> None:
            groups = load_level_groups()
            groups[group_name] = level_names
            save_level_groups(groups)

        try:
            result = generate_platforming_pack(
                group,
                count=count,
                replace=True,
                register_group=_register,
            )
        except Exception as exc:
            import traceback

            traceback.print_exc()
            self._status.configure(text=f"Regen failed: {exc}")
            self._regen_busy = False
            return

        self._regen_busy = False
        self.refresh_levels()
        self._status.configure(
            text=(
                f"Regenerated @{result.group}: {len(result.level_names)} levels "
                f"({result.path.name}/)"
            )
        )

    def _on_level_selected(self, entry: LevelEntry) -> None:
        self._preview.show_entry(entry)

    def _on_play(self, entry: LevelEntry) -> None:
        if self._play_session.active:
            self._status.configure(text="Play window already open — close it first.")
            return

        try:
            level = LevelLoader().load_level(dir_path=entry.level_dir)
        except Exception as exc:
            self._status.configure(text=f"Failed to load level: {exc}")
            return

        if level is None:
            self._status.configure(text=f"Failed to load level '{entry.name}'.")
            return

        try:
            self._play_session.start(level)
        except Exception as exc:
            self._status.configure(text=f"Failed to start play: {exc}")
            return

        self._status.configure(text=f"Playing {entry.name}…")

    def _on_play_stopped(self) -> None:
        self._status.configure(text=self._catalog_status)

    def _on_close(self) -> None:
        if self._play_session.active:
            self._play_session.stop()
        self.destroy()
