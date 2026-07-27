"""Level Archive window — hash-keyed training history for the loaded agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import customtkinter as ctk
from app.fonts import app_font
from level import Level
from level.config import LEVEL_SAVE_FOLDER_PATH
from loaders import agent_loader

from src.app.components import Minimap, MouseWheelScrollableFrame
from src.app.utils.level_minimap_geometry import parse_level_minimap_geometry
from src.config import config


class LevelArchiveWindow(ctk.CTkToplevel):
    """Toplevel listing archived training levels for the current agent."""

    COLUMNS = ("First trained", "Last trained", "Hash", "Name at first train")
    COL_WEIGHTS = (3, 3, 2, 3)

    def __init__(self, master):
        super().__init__(master)

        agent = getattr(agent_loader, "agent", None)
        self._agent_name = getattr(agent, "name", None) if agent else None
        self._agent_root: Path | None = None
        if agent is not None and getattr(agent, "trajectory_loader", None) is not None:
            self._agent_root = Path(agent.trajectory_loader.trajectory_dir).parent

        title_name = self._agent_name or "No agent"
        self.title(f"Level Archive — {title_name}")
        width = int(config.LEVEL_ARCHIVE.WINDOW_WIDTH)
        height = int(config.LEVEL_ARCHIVE.WINDOW_HEIGHT)
        self.geometry(f"{width}x{height}")
        self.resizable(True, True)
        self.lift()
        self.focus_set()

        self._hash_chars = int(config.LEVEL_ARCHIVE.HASH_DISPLAY_CHARS)
        self._selected_hash: str | None = None
        self._rows: dict[str, ctk.CTkFrame] = {}
        self._entries: list[dict[str, Any]] = []
        self._hash_cache: dict[str, tuple[float, str]] = {}
        self._copied_after_id = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkLabel(
            self,
            text="Level Archive",
            font=app_font(size=20, weight="bold"),
        )
        header.grid(row=0, column=0, columnspan=2, padx=20, pady=(16, 4), sticky="w")

        subtitle = ctk.CTkLabel(
            self,
            text=(
                f"Levels this agent trained on (focus commits). Agent: {title_name}."
            ),
            font=app_font(size=11),
            text_color="#888888",
        )
        subtitle.grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 12), sticky="w")

        table_panel = ctk.CTkFrame(self, fg_color="transparent")
        table_panel.grid(row=2, column=0, padx=(20, 8), pady=(0, 20), sticky="nsew")
        table_panel.grid_columnconfigure(0, weight=1)
        table_panel.grid_rowconfigure(1, weight=1)

        col_header = ctk.CTkFrame(
            table_panel, fg_color=("gray80", "gray20"), corner_radius=4
        )
        col_header.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        for i, (label, weight) in enumerate(zip(self.COLUMNS, self.COL_WEIGHTS)):
            col_header.grid_columnconfigure(i, weight=weight, uniform="archive")
            ctk.CTkLabel(
                col_header,
                text=label,
                anchor="w",
                font=app_font(
                    size=config.STYLE.FONT.STANDARD_SIZE,
                    weight="bold",
                ),
            ).grid(row=0, column=i, sticky="ew", padx=8, pady=6)

        self.list_frame = MouseWheelScrollableFrame(
            table_panel,
            fg_color="transparent",
        )
        self.list_frame.grid(row=1, column=0, sticky="nsew")

        self._empty_label = ctk.CTkLabel(
            self.list_frame,
            text="No archived levels yet. Train with a focus commit to populate.",
            font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
            text_color="#888888",
        )

        detail = ctk.CTkFrame(self, fg_color="transparent")
        detail.grid(row=2, column=1, padx=(8, 20), pady=(0, 20), sticky="nsew")
        detail.grid_columnconfigure(0, weight=1)
        detail.grid_rowconfigure(0, weight=2)
        detail.grid_rowconfigure(1, weight=1)

        self.minimap = Minimap(detail)
        self.minimap.grid(row=0, column=0, sticky="nsew", pady=(0, 8))

        matches_panel = ctk.CTkFrame(detail, fg_color=("gray90", "gray17"), corner_radius=8)
        matches_panel.grid(row=1, column=0, sticky="nsew")
        matches_panel.grid_columnconfigure(0, weight=1)
        matches_panel.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            matches_panel,
            text="Matching level saves",
            font=app_font(size=14, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=12, pady=(12, 4), sticky="w")

        self.matches_list = MouseWheelScrollableFrame(
            matches_panel,
            fg_color="transparent",
        )
        self.matches_list.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")

        self._matches_empty = ctk.CTkLabel(
            self.matches_list,
            text="Select a level to find matching saves.",
            font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
            text_color="#888888",
        )
        self._matches_empty.pack(anchor="w", padx=4, pady=4)

        self._clipboard_status = ctk.CTkLabel(
            self,
            text="",
            font=app_font(size=11),
            text_color="#10b981",
        )
        self._clipboard_status.grid(
            row=3, column=0, columnspan=2, padx=20, pady=(0, 12), sticky="w"
        )

        self._load_entries()
        if self._entries:
            self._select(self._entries[0]["hash"])
        else:
            self._empty_label.pack(anchor="w", padx=4, pady=8)

    def _load_entries(self) -> None:
        archive: dict[str, Any] = {}
        if self._agent_root is not None:
            meta_path = self._agent_root / "trajectories" / "metadata.json"
            if meta_path.is_file():
                try:
                    with open(meta_path, "r") as f:
                        metadata = json.load(f)
                    raw = metadata.get("level_archive") or {}
                    if isinstance(raw, dict):
                        archive = raw
                except Exception:
                    archive = {}

        entries: list[dict[str, Any]] = []
        for digest, info in archive.items():
            if not digest or not isinstance(info, dict):
                continue
            entries.append(
                {
                    "hash": str(digest),
                    "name_at_first_train": str(
                        info.get("name_at_first_train") or "unknown"
                    ),
                    "first_trained_at": str(info.get("first_trained_at") or ""),
                    "last_trained_at": str(info.get("last_trained_at") or ""),
                }
            )

        entries.sort(key=lambda e: e.get("last_trained_at") or "", reverse=True)
        self._entries = entries
        for entry in entries:
            self._create_row(entry)

    @staticmethod
    def _format_datetime(value: str) -> str:
        if not value:
            return "—"
        return value.replace("T", " ").replace("+00:00", " UTC")

    def _truncate_hash(self, digest: str) -> str:
        if len(digest) <= self._hash_chars:
            return digest
        return digest[: self._hash_chars]

    def _create_row(self, entry: dict[str, Any]) -> ctk.CTkFrame:
        entry_hash = entry["hash"]
        row = ctk.CTkFrame(
            self.list_frame,
            fg_color="transparent",
            corner_radius=4,
            cursor="hand2",
        )
        values = (
            self._format_datetime(entry.get("first_trained_at", "")),
            self._format_datetime(entry.get("last_trained_at", "")),
            self._truncate_hash(entry_hash),
            str(entry.get("name_at_first_train") or "unknown"),
        )
        for i, (text, weight) in enumerate(zip(values, self.COL_WEIGHTS)):
            row.grid_columnconfigure(i, weight=weight, uniform="archive")
            label = ctk.CTkLabel(
                row,
                text=text,
                anchor="w",
                font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
            )
            label.grid(row=0, column=i, sticky="ew", padx=8, pady=4)

            def on_select(_event=None, selected=entry_hash):
                self._select(selected)

            label.bind("<Button-1>", on_select)
            if i == 2:
                label.configure(cursor="hand2", text_color=("#2563eb", "#60a5fa"))

                def on_copy(_event=None, full=entry_hash):
                    self._select(full)
                    self._copy_hash(full)

                label.bind("<Button-1>", on_copy)

        def on_select_row(_event=None, selected=entry_hash):
            self._select(selected)

        row.bind("<Button-1>", on_select_row)
        self.list_frame.bind_scroll_events_recursively(row)
        row.pack(fill="x", pady=1)
        self._rows[entry_hash] = row
        return row

    def _select(self, entry_hash: str) -> None:
        previous = self._rows.get(self._selected_hash) if self._selected_hash else None
        if previous is not None:
            previous.configure(fg_color="transparent")

        self._selected_hash = entry_hash
        row = self._rows.get(entry_hash)
        if row is not None:
            row.configure(fg_color=("gray75", "gray25"))

        self._show_detail(entry_hash)

    def _copy_hash(self, digest: str) -> None:
        try:
            self.clipboard_clear()
            self.clipboard_append(digest)
            self._clipboard_status.configure(text="Hash copied to clipboard.")
        except Exception:
            self._clipboard_status.configure(text="Could not copy hash.")
            return

        if self._copied_after_id is not None:
            try:
                self.after_cancel(self._copied_after_id)
            except Exception:
                pass
        self._copied_after_id = self.after(2000, self._clear_clipboard_status)

    def _clear_clipboard_status(self) -> None:
        self._copied_after_id = None
        self._clipboard_status.configure(text="")

    def _show_detail(self, entry_hash: str) -> None:
        self._update_minimap(entry_hash)
        self._update_matches(entry_hash)

    def _update_minimap(self, entry_hash: str) -> None:
        if self._agent_root is None:
            self.minimap.reset_to_default()
            return

        level_path = self._agent_root / "level_saves" / f"{entry_hash}.json"
        if not level_path.is_file():
            self.minimap.reset_to_default()
            return

        try:
            with open(level_path, "r") as f:
                level_data = json.load(f)
            geom = parse_level_minimap_geometry(level_data)
            self.minimap.set_level(
                geom.grid_size,
                geom.tile_size,
                geom.walls,
                geom.start_pos,
                geom.goal_pos,
                level_hash=entry_hash,
            )
        except Exception:
            self.minimap.reset_to_default()

    def _update_matches(self, entry_hash: str) -> None:
        for child in self.matches_list.winfo_children():
            child.destroy()

        matches = self._find_matching_global_levels(entry_hash)
        if not matches:
            empty = ctk.CTkLabel(
                self.matches_list,
                text="No current level saves match this hash.",
                font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
                text_color="#888888",
            )
            empty.pack(anchor="w", padx=4, pady=4)
            return

        for name in matches:
            label = ctk.CTkLabel(
                self.matches_list,
                text=name,
                anchor="w",
                font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
            )
            label.pack(anchor="w", padx=4, pady=2)
            self.matches_list.bind_scroll_events_recursively(label)

    def _find_matching_global_levels(self, target_hash: str) -> list[str]:
        root = Path(LEVEL_SAVE_FOLDER_PATH)
        if not root.is_dir():
            return []

        matches: list[str] = []
        for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if not child.is_dir():
                continue
            level_json = child / "level.json"
            if not level_json.is_file():
                continue
            digest = self._hash_for_path(level_json)
            if digest == target_hash:
                matches.append(child.name)
        return matches

    def _hash_for_path(self, path: Path) -> str | None:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return None

        key = str(path)
        cached = self._hash_cache.get(key)
        if cached is not None and cached[0] == mtime:
            return cached[1]

        try:
            with open(path, "r") as f:
                level_data = json.load(f)
            digest = Level.hash_json(level_data)
        except Exception:
            return None

        self._hash_cache[key] = (mtime, digest)
        return digest
