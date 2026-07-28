import customtkinter as ctk
from app.components import MessageOverlay
from app.fonts import app_font
from loaders import agent_loader
from app.utils import verify_level_issues
from app.components import StandardButton
from src.config import config
from typing import TYPE_CHECKING, cast

from ..run_grid import RunGrid
from ._hover_arrow_nav import HoverArrowNav

if TYPE_CHECKING:
    from ..trajectory_viewer import TrajectoryViewer


def _cfg(name: str, default):
    try:
        return getattr(config.RUN_GRID, name)
    except AttributeError:
        return default


class TrajectoryHeader(ctk.CTkFrame):
    """
    Header for the TrajectoryViewer: run index entry, Live/Replay, primary
    run grid, and a short secondary scrubber with run/level nav arrows.
    """

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.current_index = None
        from loaders import agent_loader as _agent_loader

        self.live_var = ctk.BooleanVar(value=bool(_agent_loader.live))
        self.scrub_width = int(_cfg("SCRUB_WIDTH", 160))

        self.grid_columnconfigure(0, weight=1)

        self.controls = ctk.CTkFrame(self, fg_color="transparent")
        self.controls.grid(row=0, column=0, sticky="w", pady=(0, 4))

        self.label = ctk.CTkLabel(
            self.controls,
            text="Run:",
            font=app_font(size=config.STYLE.FONT.STANDARD_SIZE, weight="bold"),
        )
        self.label.pack(side="left", padx=(0, 4))

        self.index_entry = ctk.CTkEntry(
            self.controls,
            width=64,
            justify="center",
            font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        self.index_entry.pack(side="left", padx=2)
        self.index_entry.bind("<Return>", lambda e: self._on_entry_submit())
        self.index_entry.bind("<FocusOut>", lambda e: self._on_entry_submit())

        self.total_label = ctk.CTkLabel(
            self.controls,
            text="/ 0",
            font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        self.total_label.pack(side="left", padx=4)

        self.live_checkbox = ctk.CTkCheckBox(
            self.controls,
            text="Live",
            variable=self.live_var,
            command=self._on_live_toggled,
            checkbox_width=20,
            checkbox_height=20,
            font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        self.live_checkbox.pack(side="left", padx=(12, 4))

        self.replay_button = StandardButton(
            self.controls, text="Replay", command=self._replay, width=80
        )
        self.replay_button.pack(side="left", padx=(8, 4))

        self.run_grid = RunGrid(
            self,
            on_select=self._on_grid_select,
            on_replay=self._on_grid_replay,
        )
        self.run_grid.grid(row=1, column=0, sticky="ew", pady=(0, 4))

        self.scrub_row = ctk.CTkFrame(self, fg_color="transparent")
        self.scrub_row.grid(row=2, column=0, sticky="w", pady=(4, 4))

        btn_kw = dict(width=28, height=22, font=app_font(size=11))

        self.prev_landmark_btn = ctk.CTkButton(
            self.scrub_row, text="◀◀", command=self._on_prev_landmark, **btn_kw
        )
        self.prev_landmark_btn.pack(side="left", padx=(0, 2))

        self.prev_run_btn = ctk.CTkButton(
            self.scrub_row, text="◀", command=self._on_prev_run, **btn_kw
        )
        self.prev_run_btn.pack(side="left", padx=(0, 4))

        self.slider = ctk.CTkSlider(
            self.scrub_row,
            from_=1,
            to=1,
            number_of_steps=1,
            width=self.scrub_width,
            height=14,
            command=self._on_slider_drag,
        )
        self.slider.pack(side="left")

        self.next_run_btn = ctk.CTkButton(
            self.scrub_row, text="▶", command=self._on_next_run, **btn_kw
        )
        self.next_run_btn.pack(side="left", padx=(4, 2))

        self.next_landmark_btn = ctk.CTkButton(
            self.scrub_row, text="▶▶", command=self._on_next_landmark, **btn_kw
        )
        self.next_landmark_btn.pack(side="left", padx=(0, 0))

        self.slider.bind("<ButtonRelease-1>", lambda e: self._on_slider_release())
        self.slider.bind("<MouseWheel>", self._on_mouse_wheel)
        self.slider.bind("<Button-4>", self._on_mouse_wheel)
        self.slider.bind("<Button-5>", self._on_mouse_wheel)

        self.hover_nav = HoverArrowNav(self)
        self.after_idle(self.hover_nav.install)

        from state_managers import trajectory_stats_state_manager

        trajectory_stats_state_manager.add_on_trajectory_added_callback(
            self.refresh_from_metadata
        )
        trajectory_stats_state_manager.add_on_refresh_stats_callback(
            self.refresh_from_metadata
        )

        self.refresh_from_metadata()
        agent_loader.add_prefs_listener(self._sync_live_from_loader)

    def _sync_live_from_loader(self):
        enabled = bool(agent_loader.live)
        if bool(self.live_var.get()) != enabled:
            self.live_var.set(enabled)
        self.run_grid.set_live_mode(enabled)
        if enabled:
            total = self.total_trajectories
            if total > 0:
                self.load_trajectory_by_index(total - 1)

    def set_header_width(self, width: int):
        """Update run-grid layout width. Scrub stays a short fixed secondary control."""
        self.run_grid.set_width(max(160, int(width)))

    def set_slider_width(self, width: int):
        self.set_header_width(width)

    @property
    def total_trajectories(self) -> int:
        """Gets total trajectories directly from metadata json."""
        import json

        try:
            metadata_path = self.trajectory_loader.trajectory_dir / "metadata.json"
            if metadata_path.is_file():
                with open(metadata_path, "r") as f:
                    return json.load(f).get("trajectory_count", 0)
        except Exception:
            pass
        return 0

    def refresh_from_metadata(self):
        """Refreshes total trajectory count and updates ranges/positions."""
        total = self.total_trajectories
        self.total_label.configure(text=f"/ {total}")
        self.run_grid.refresh_from_disk()
        self.run_grid.set_live_mode(bool(self.live_var.get()))

        if total > 0:
            if total > 1:
                self.slider.configure(
                    state="normal", from_=1, to=total, number_of_steps=total - 1
                )
            else:
                self.slider.configure(
                    state="disabled", from_=1, to=1.001, number_of_steps=1
                )

            if self.live_var.get() or self.current_index is None:
                latest = total - 1
                if self.current_index != latest:
                    self.load_trajectory_by_index(latest)
                else:
                    self._update_ui_state()
            elif self.current_index >= total:
                self.load_trajectory_by_index(total - 1)
            else:
                self._update_ui_state()
        else:
            self.current_index = None
            self.slider.configure(state="disabled", from_=0, to=1, number_of_steps=1)
            self.slider.set(0)
            self.index_entry.delete(0, "end")
            self.index_entry.insert(0, "0")
            self.replay_button.configure(state="disabled")
            self.run_grid.set_selected_index(None)

    def _on_live_toggled(self):
        enabled = bool(self.live_var.get())
        agent_loader.set_live(enabled)
        self.run_grid.set_live_mode(enabled)
        if not enabled:
            return
        total = self.total_trajectories
        if total > 0:
            self.load_trajectory_by_index(total - 1)

    def _disable_live(self):
        if self.live_var.get():
            self.live_var.set(False)
            agent_loader.set_live(False)
            self.run_grid.set_live_mode(False)

    def _on_grid_select(self, index: int):
        self._disable_live()
        self.load_trajectory_by_index(index)

    def _on_grid_replay(self, index: int):
        self._disable_live()
        if self.load_trajectory_by_index(index):
            self._replay()

    def _on_prev_run(self):
        self._disable_live()
        self.run_grid.jump_prev_run()

    def _on_next_run(self):
        self._disable_live()
        self.run_grid.jump_next_run()

    def _on_prev_landmark(self):
        self._disable_live()
        self.run_grid.jump_prev_landmark()

    def _on_next_landmark(self):
        self._disable_live()
        self.run_grid.jump_next_landmark()

    def _on_slider_drag(self, value):
        self.index_entry.delete(0, "end")
        self.index_entry.insert(0, str(int(value)))

    def _on_slider_release(self):
        self._disable_live()
        val = int(self.slider.get())
        self.load_trajectory_by_index(val - 1)

    def _on_mouse_wheel(self, event):
        total = self.total_trajectories
        if total <= 0:
            return
        current_val = self.slider.get()
        if event.num == 5 or event.delta < 0:
            new_val = current_val - 1
        elif event.num == 4 or event.delta > 0:
            new_val = current_val + 1
        else:
            return

        if new_val < 1:
            new_val = 1
        elif new_val > total:
            new_val = total

        target_index = int(new_val) - 1
        if target_index == self.current_index:
            return

        self._disable_live()
        self.slider.set(new_val)
        self._on_slider_drag(new_val)
        self.load_trajectory_by_index(target_index)

    def _on_entry_submit(self):
        total = self.total_trajectories
        if total <= 0:
            self.index_entry.delete(0, "end")
            self.index_entry.insert(0, "0")
            return

        entry_val = self.index_entry.get()
        try:
            val = int(entry_val)
            if val < 1:
                val = 1
            elif val > total:
                val = total
        except ValueError:
            val = (self.current_index + 1) if self.current_index is not None else 1

        if not (
            self.live_var.get()
            and self.current_index is not None
            and val - 1 == self.current_index
        ):
            self._disable_live()
        self.load_trajectory_by_index(val - 1)

    def load_trajectory_by_index(self, index: int) -> bool:
        """Loads trajectory from files and displays its JSON content."""
        self.master = cast("TrajectoryViewer", self.master)

        trajectory = self.trajectory_loader.load_trajectory(index)
        if trajectory is None:
            return False

        self.master.trajectory = trajectory
        self.master.display_trajectory()

        self.current_index = index
        self._update_ui_state()
        return True

    def _update_ui_state(self):
        total = self.total_trajectories
        if self.current_index is not None and total > 0:
            self.replay_button.configure(state="normal")
            display_val = self.current_index + 1
            self.index_entry.delete(0, "end")
            self.index_entry.insert(0, str(display_val))
            self.slider.set(display_val)
            self.run_grid.set_selected_index(self.current_index)
            self.run_grid.set_live_mode(bool(self.live_var.get()))
        else:
            self.replay_button.configure(state="disabled")
            self.run_grid.set_selected_index(None)

    def _replay(self):
        from app_manager import app_manager

        self.master = cast("TrajectoryViewer", self.master)

        if self.master.trajectory is None:
            MessageOverlay(
                "Please load a trajectory before replaying.", subject="Error"
            )
            return

        if not verify_level_issues():
            app_manager.start_replay()

    @property
    def trajectory_loader(self):
        return agent_loader.agent.trajectory_loader
