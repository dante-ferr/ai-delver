import json
from pathlib import Path

import customtkinter as ctk
from app.fonts import app_font
from src.config import config


class TrajectorySummaryPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="#2b2b2b", corner_radius=8, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._hash_cache: dict[str, tuple[float, str]] = {}
        self._current_hash: str = ""
        self._copied_after_id = None

        # Title
        self.summary_title = ctk.CTkLabel(
            self, text="Run Summary", font=app_font(size=14, weight="bold")
        )
        self.summary_title.pack(anchor="w", padx=12, pady=(8, 2))

        # Stats Container
        self.stats_container = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_container.pack(fill="x", padx=12, pady=2)

        self.status_label = ctk.CTkLabel(
            self.stats_container,
            text="Select a cycle to view stats.",
            font=app_font(size=13),
            justify="left",
        )
        self.status_label.pack(anchor="w", pady=2)

        # Details Grid for cycle stats
        self.details_grid = ctk.CTkFrame(self.stats_container, fg_color="transparent")
        self.details_grid.grid_columnconfigure(1, weight=1)

        key_font = app_font(size=12, weight="bold")
        val_font = app_font(size=12)

        # Outcome
        ctk.CTkLabel(
            self.details_grid, text="Outcome:", font=key_font, text_color="#aaaaaa"
        ).grid(row=0, column=0, sticky="w", padx=(0, 8), pady=0)
        self.outcome_val = ctk.CTkLabel(
            self.details_grid, text="", font=val_font, anchor="w"
        )
        self.outcome_val.grid(row=0, column=1, sticky="w", pady=0)

        # Duration
        ctk.CTkLabel(
            self.details_grid, text="Duration:", font=key_font, text_color="#aaaaaa"
        ).grid(row=1, column=0, sticky="w", padx=(0, 8), pady=0)
        self.duration_val = ctk.CTkLabel(
            self.details_grid, text="", font=val_font, anchor="w"
        )
        self.duration_val.grid(row=1, column=1, sticky="w", pady=0)

        # Reward
        ctk.CTkLabel(
            self.details_grid, text="Reward:", font=key_font, text_color="#aaaaaa"
        ).grid(row=2, column=0, sticky="w", padx=(0, 8), pady=0)
        self.reward_val = ctk.CTkLabel(
            self.details_grid, text="", font=val_font, anchor="w"
        )
        self.reward_val.grid(row=2, column=1, sticky="w", pady=0)

        # Level Hash
        ctk.CTkLabel(
            self.details_grid, text="Hash:", font=key_font, text_color="#aaaaaa"
        ).grid(row=3, column=0, sticky="w", padx=(0, 8), pady=0)

        self.hash_container = ctk.CTkFrame(self.details_grid, fg_color="transparent")
        self.hash_container.grid(row=3, column=1, sticky="w", pady=0)

        self.hash_val = ctk.CTkLabel(
            self.hash_container,
            text="",
            font=val_font,
            text_color=("#2563eb", "#60a5fa"),
            cursor="hand2",
            anchor="w",
        )
        self.hash_val.pack(side="left")
        self.hash_val.bind("<Button-1>", self._on_hash_clicked)

        self.clipboard_status_label = ctk.CTkLabel(
            self.hash_container,
            text="",
            font=app_font(size=11),
            text_color="#10b981",
        )
        self.clipboard_status_label.pack(side="left", padx=(8, 0))

        # Name at first train
        ctk.CTkLabel(
            self.details_grid, text="1st Train Name:", font=key_font, text_color="#aaaaaa"
        ).grid(row=4, column=0, sticky="w", padx=(0, 8), pady=0)
        self.first_train_val = ctk.CTkLabel(
            self.details_grid, text="", font=val_font, anchor="w"
        )
        self.first_train_val.grid(row=4, column=1, sticky="w", pady=0)

        # Matching Saves
        ctk.CTkLabel(
            self.details_grid, text="Matching Saves:", font=key_font, text_color="#aaaaaa"
        ).grid(row=5, column=0, sticky="w", padx=(0, 8), pady=0)
        self.matching_val = ctk.CTkLabel(
            self.details_grid, text="", font=val_font, anchor="w"
        )
        self.matching_val.grid(row=5, column=1, sticky="w", pady=0)

        # Timeline Title
        self.timeline_title = ctk.CTkLabel(
            self, text="Action Timeline", font=app_font(size=12, weight="bold")
        )
        self.timeline_title.pack(anchor="w", padx=12, pady=(6, 2))

        # Scrollable Textbox for timeline events
        self.timeline_display = ctk.CTkTextbox(self, wrap="none")
        self.timeline_display.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _truncate_hash(self, digest: str) -> str:
        if not digest:
            return "—"
        try:
            hash_chars = int(config.LEVEL_ARCHIVE.HASH_DISPLAY_CHARS)
        except Exception:
            hash_chars = 12
        if len(digest) <= hash_chars:
            return digest
        return digest[:hash_chars]

    def _on_hash_clicked(self, _event=None):
        if not self._current_hash:
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(self._current_hash)
            self.clipboard_status_label.configure(text="Copied!")
        except Exception:
            self.clipboard_status_label.configure(text="Could not copy")
            return

        if self._copied_after_id is not None:
            try:
                self.after_cancel(self._copied_after_id)
            except Exception:
                pass
        self._copied_after_id = self.after(2000, self._clear_clipboard_status)

    def _clear_clipboard_status(self):
        self._copied_after_id = None
        if hasattr(self, "clipboard_status_label") and self.clipboard_status_label.winfo_exists():
            self.clipboard_status_label.configure(text="")

    def _get_name_at_first_train(self, target_hash: str) -> str:
        if not target_hash:
            return "unknown"

        try:
            from loaders import agent_loader
            agent = getattr(agent_loader, "agent", None)
            if agent is None or getattr(agent, "trajectory_loader", None) is None:
                return "unknown"

            trajectory_dir = Path(agent.trajectory_loader.trajectory_dir)
            meta_paths = [
                trajectory_dir / "metadata.json",
                trajectory_dir.parent / "trajectories" / "metadata.json",
            ]

            metadata = None
            for meta_path in meta_paths:
                if meta_path.is_file():
                    try:
                        with open(meta_path, "r") as f:
                            metadata = json.load(f)
                        break
                    except Exception:
                        continue

            if not isinstance(metadata, dict):
                return "unknown"

            # Check level_archive
            archive = metadata.get("level_archive")
            if isinstance(archive, dict):
                info = archive.get(target_hash)
                if isinstance(info, dict) and info.get("name_at_first_train"):
                    return str(info["name_at_first_train"])

            # Fallback to level_hashes mapping
            hashes = metadata.get("level_hashes")
            if isinstance(hashes, dict):
                for name, digest in hashes.items():
                    if digest == target_hash:
                        return str(name)
        except Exception:
            pass

        return "unknown"

    def _find_matching_global_levels(self, target_hash: str) -> list[str]:
        if not target_hash:
            return []

        try:
            from level.config import LEVEL_SAVE_FOLDER_PATH
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
        except Exception:
            return []

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
            from level import Level
            digest = Level.hash_json(level_data)
        except Exception:
            return None

        self._hash_cache[key] = (mtime, digest)
        return digest

    def update_summary(self, trajectory):
        """Updates the text statistics and action timeline from the trajectory."""
        self.status_label.pack_forget()
        self.details_grid.pack(fill="x", padx=0, pady=2)

        outcome_str = "🏆 VICTORIOUS" if trajectory.victorious else "💀 DEFEATED"
        outcome_color = "#10b981" if trajectory.victorious else "#ef4444"

        total_frames = len(trajectory.frame_snapshots)
        dur_secs = (
            total_frames / trajectory.actions_per_second
            if trajectory.actions_per_second > 0
            else 0.0
        )

        reward = trajectory.total_reward
        reward_str = f"{reward:.4f}" if reward is not None else "N/A"

        self.outcome_val.configure(text=outcome_str, text_color=outcome_color)
        self.duration_val.configure(text=f"{dur_secs:.2f}s ({total_frames} frames)")
        self.reward_val.configure(text=reward_str)

        level_hash = getattr(trajectory, "level_hash", "") or ""
        self._current_hash = level_hash
        truncated_hash = self._truncate_hash(level_hash)

        if level_hash:
            self.hash_val.configure(
                text=truncated_hash,
                text_color=("#2563eb", "#60a5fa"),
                cursor="hand2",
            )
        else:
            self.hash_val.configure(
                text="—",
                text_color=("#333333", "#cccccc"),
                cursor="",
            )
        self.clipboard_status_label.configure(text="")

        first_train_name = self._get_name_at_first_train(level_hash)
        self.first_train_val.configure(text=first_train_name)

        matches = self._find_matching_global_levels(level_hash)
        matching_str = ", ".join(matches) if matches else "None"
        self.matching_val.configure(text=matching_str)

        # Update timeline display
        self.timeline_display.configure(state="normal")
        self.timeline_display.delete("1.0", "end")

        timeline = []
        prev_action = None
        for i, action in enumerate(trajectory.delver_actions):
            t = (
                i / trajectory.actions_per_second
                if trajectory.actions_per_second > 0
                else 0.0
            )

            run_val = action.get("run", 0)
            jump_val = action.get("jump", False)

            # Log changes in action intent
            is_different = (
                prev_action is None
                or prev_action.get("run", 0) != run_val
                or prev_action.get("jump", False) != jump_val
            )

            if is_different:
                action_desc = []
                if run_val == 1:
                    action_desc.append("Run Right 👉")
                elif run_val == -1:
                    action_desc.append("Run Left 👈")

                if jump_val:
                    action_desc.append("Jump 🦘")

                if not action_desc:
                    action_desc.append("Idle 🧘")

                timeline.append(f"{t:.1f}s: " + " + ".join(action_desc))
                prev_action = action

        self.timeline_display.insert("1.0", "\n".join(timeline))
        self.timeline_display.configure(state="disabled")

    def reset_to_default(self):
        self._current_hash = ""
        self.details_grid.pack_forget()
        self.status_label.configure(
            text="Select a cycle to view stats.", text_color="#ffffff"
        )
        self.status_label.pack(anchor="w", pady=4)
        self.timeline_display.configure(state="normal")
        self.timeline_display.delete("1.0", "end")
        self.timeline_display.insert(
            "1.0",
            "Trajectory actions will be listed here chronologically once loaded."
        )
        self.timeline_display.configure(state="disabled")

