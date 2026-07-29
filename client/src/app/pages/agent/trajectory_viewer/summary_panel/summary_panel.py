import customtkinter as ctk
from app.fonts import app_font

from ._action_sequence_popup import ActionSequencePopup
from ._level_meta import LevelMetaLookup


from app.theme import theme

class TrajectorySummaryPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=theme.bg_dark, corner_radius=8, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)

        self._hash_cache: dict[str, tuple[float, str]] = {}
        self._current_hash: str = ""
        self._copied_after_id = None
        self.level_meta = LevelMetaLookup(self)

        self.summary_title = ctk.CTkLabel(
            self,
            text="Run Summary",
            font=app_font(size=14, weight="bold"),
            text_color=theme.primary_color,
        )
        self.summary_title.pack(anchor="w", padx=12, pady=(8, 2))

        self.stats_container = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_container.pack(fill="x", padx=12, pady=2)

        self.status_label = ctk.CTkLabel(
            self.stats_container,
            text="Select a cycle to view stats.",
            font=app_font(size=13),
            text_color=theme.text_light,
            justify="left",
        )
        self.status_label.pack(anchor="w", pady=2)

        self.details_grid = ctk.CTkFrame(self.stats_container, fg_color="transparent")
        self.details_grid.grid_columnconfigure(1, weight=1)

        key_font = app_font(size=12, weight="bold")
        val_font = app_font(size=12)

        ctk.CTkLabel(
            self.details_grid, text="Outcome:", font=key_font, text_color=theme.text_slate
        ).grid(row=0, column=0, sticky="w", padx=(0, 8), pady=0)
        self.outcome_val = ctk.CTkLabel(
            self.details_grid, text="", font=val_font, text_color=theme.text_light, anchor="w"
        )
        self.outcome_val.grid(row=0, column=1, sticky="w", pady=0)

        ctk.CTkLabel(
            self.details_grid, text="Duration:", font=key_font, text_color=theme.text_slate
        ).grid(row=1, column=0, sticky="w", padx=(0, 8), pady=0)
        self.duration_val = ctk.CTkLabel(
            self.details_grid, text="", font=val_font, text_color=theme.text_light, anchor="w"
        )
        self.duration_val.grid(row=1, column=1, sticky="w", pady=0)

        ctk.CTkLabel(
            self.details_grid, text="Reward:", font=key_font, text_color=theme.text_slate
        ).grid(row=2, column=0, sticky="w", padx=(0, 8), pady=0)
        self.reward_val = ctk.CTkLabel(
            self.details_grid, text="", font=val_font, text_color=theme.text_light, anchor="w"
        )
        self.reward_val.grid(row=2, column=1, sticky="w", pady=0)

        ctk.CTkLabel(
            self.details_grid, text="Hash:", font=key_font, text_color=theme.text_slate
        ).grid(row=3, column=0, sticky="w", padx=(0, 8), pady=0)

        self.hash_container = ctk.CTkFrame(self.details_grid, fg_color="transparent")
        self.hash_container.grid(row=3, column=1, sticky="w", pady=0)

        self.hash_val = ctk.CTkLabel(
            self.hash_container,
            text="",
            font=val_font,
            text_color=("#2563eb", theme.primary_color),
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

        ctk.CTkLabel(
            self.details_grid, text="1st Train Name:", font=key_font, text_color=theme.text_slate
        ).grid(row=4, column=0, sticky="w", padx=(0, 8), pady=0)
        self.first_train_val = ctk.CTkLabel(
            self.details_grid, text="", font=val_font, text_color=theme.text_light, anchor="w"
        )
        self.first_train_val.grid(row=4, column=1, sticky="w", pady=0)

        ctk.CTkLabel(
            self.details_grid, text="Matching Saves:", font=key_font, text_color=theme.text_slate
        ).grid(row=5, column=0, sticky="w", padx=(0, 8), pady=0)
        self.matching_val = ctk.CTkLabel(
            self.details_grid, text="", font=val_font, text_color=theme.text_light, anchor="w"
        )
        self.matching_val.grid(row=5, column=1, sticky="w", pady=0)

        ctk.CTkLabel(
            self.details_grid, text="Jump Takeoffs:", font=key_font, text_color=theme.text_slate
        ).grid(row=6, column=0, sticky="w", padx=(0, 8), pady=0)
        self.takeoffs_val = ctk.CTkLabel(
            self.details_grid, text="", font=val_font, text_color=theme.text_light, anchor="w"
        )
        self.takeoffs_val.grid(row=6, column=1, sticky="w", pady=0)

        ctk.CTkLabel(
            self.details_grid, text="Confidence:", font=key_font, text_color=theme.text_slate
        ).grid(row=7, column=0, sticky="w", padx=(0, 8), pady=0)
        self.confidence_val = ctk.CTkLabel(
            self.details_grid, text="", font=val_font, text_color=theme.text_light, anchor="w"
        )
        self.confidence_val.grid(row=7, column=1, sticky="w", pady=0)

        ctk.CTkLabel(
            self.details_grid, text="Kind:", font=key_font, text_color=theme.text_slate
        ).grid(row=8, column=0, sticky="w", padx=(0, 8), pady=0)
        self.kind_val = ctk.CTkLabel(
            self.details_grid, text="", font=val_font, text_color=theme.text_light, anchor="w"
        )
        self.kind_val.grid(row=8, column=1, sticky="w", pady=0)

        self.actions_btn = ctk.CTkButton(
            self.stats_container,
            text="Action Sequence…",
            width=140,
            height=26,
            font=app_font(size=12),
            command=self._open_action_sequence_popup,
            state="disabled",
        )
        self.actions_btn.pack(anchor="w", pady=(4, 8))

        self._timeline_text = ""
        self._action_popup = None

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

    def update_summary(self, trajectory):
        if trajectory is None:
            self.reset_to_default()
            return

        if self.status_label.winfo_ismapped():
            self.status_label.pack_forget()
        if not self.details_grid.winfo_ismapped():
            self.details_grid.pack(fill="x", padx=12, pady=(2, 12))
        if not self.actions_btn.winfo_ismapped():
            self.actions_btn.pack(anchor="w", padx=12, pady=(4, 8))

        outcome_str = "🏆 VICTORIOUS" if trajectory.victorious else "💀 DEFEATED"
        outcome_color = "#10b981" if trajectory.victorious else theme.primary_color

        total_frames = len(trajectory.frame_snapshots)
        dur_secs = (
            total_frames / trajectory.actions_per_second
            if trajectory.actions_per_second > 0
            else 0.0
        )

        reward_val = getattr(trajectory, "total_reward", 0.0)
        reward_str = f"{reward_val:+.2f}"

        self.outcome_val.configure(text=outcome_str, text_color=outcome_color)
        self.duration_val.configure(
            text=f"{dur_secs:.2f}s ({total_frames} frames)", text_color=theme.text_light
        )
        self.reward_val.configure(text=reward_str, text_color=theme.text_light)

        level_hash = getattr(trajectory, "level_hash", "") or ""
        self._current_hash = level_hash
        truncated_hash = self.level_meta.truncate_hash(level_hash)

        if level_hash:
            self.hash_val.configure(
                text=truncated_hash,
                text_color=("#2563eb", theme.primary_color),
            )
        else:
            self.hash_val.configure(
                text="—",
                text_color=("#333333", theme.text_slate),
            )
        self.clipboard_status_label.configure(text="")

        first_train_name = self.level_meta.get_name_at_first_train(level_hash)
        self.first_train_val.configure(text=first_train_name, text_color=theme.text_light)

        matches = self.level_meta.find_matching_global_levels(level_hash)
        matching_str = ", ".join(matches) if matches else "None"
        self.matching_val.configure(text=matching_str, text_color=theme.text_light)

        takeoffs = getattr(trajectory, "jump_takeoffs", None)
        self.takeoffs_val.configure(
            text=str(takeoffs) if takeoffs is not None else "N/A",
            text_color=theme.text_light,
        )

        confidence = getattr(trajectory, "policy_confidence", None)
        if isinstance(confidence, (int, float)):
            self.confidence_val.configure(text=f"{float(confidence):.3f}", text_color=theme.text_light)
        else:
            self.confidence_val.configure(text="N/A", text_color=theme.text_light)

        kind = getattr(trajectory, "kind", None) or "train"
        self.kind_val.configure(text=str(kind), text_color=theme.text_light)

        self._timeline_text = self._build_action_timeline(trajectory)
        self.actions_btn.configure(state="normal")
        if self._action_popup is not None and self._action_popup.winfo_exists():
            self._action_popup.set_timeline(self._timeline_text)

    @staticmethod
    def _build_action_timeline(trajectory) -> str:
        timeline = []
        prev_action = None
        actions = getattr(trajectory, "delver_actions", None) or []
        aps = getattr(trajectory, "actions_per_second", 0) or 0
        for i, action in enumerate(actions):
            t = i / aps if aps > 0 else 0.0

            run_val = action.get("run", 0)
            jump_val = action.get("jump", False)

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

        return "\n".join(timeline) if timeline else "(no actions)"

    def _open_action_sequence_popup(self):
        if self._action_popup is not None and self._action_popup.winfo_exists():
            self._action_popup.set_timeline(self._timeline_text)
            self._action_popup.lift()
            self._action_popup.focus_set()
            return
        self._action_popup = ActionSequencePopup(self, self._timeline_text)

    def reset_to_default(self):
        self._current_hash = ""
        self._timeline_text = ""
        self.actions_btn.configure(state="disabled")
        self.details_grid.pack_forget()
        self.status_label.configure(
            text="Select a cycle to view stats.", text_color="#ffffff"
        )
        self.status_label.pack(anchor="w", pady=4)
        if self._action_popup is not None and self._action_popup.winfo_exists():
            self._action_popup.set_timeline(
                "Trajectory actions will be listed here chronologically once loaded."
            )
