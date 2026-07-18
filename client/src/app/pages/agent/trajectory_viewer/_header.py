import customtkinter as ctk
from app.components import MessageOverlay
from loaders import agent_loader
from app.utils import verify_level_issues
from app.components import StandardButton
from src.config import config
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from .trajectory_viewer import TrajectoryViewer


class TrajectoryHeader(ctk.CTkFrame):
    """
    The header component for the TrajectoryViewer, providing UI for loading
    a specific trajectory by index and initiating a replay.
    """

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.current_index = None

        # Row 0: controls
        self.label = ctk.CTkLabel(
            self, text="Episode:", font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE, weight="bold")
        )
        self.label.grid(row=0, column=0, padx=(0, 4), pady=(0, 4), sticky="w")

        # Entry for typing index (1-based)
        self.index_entry = ctk.CTkEntry(
            self,
            width=64,
            justify="center",
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        self.index_entry.grid(row=0, column=1, padx=2, pady=(0, 4), sticky="w")
        self.index_entry.bind("<Return>", lambda e: self._on_entry_submit())
        self.index_entry.bind("<FocusOut>", lambda e: self._on_entry_submit())

        # Total label showing "/ {total}"
        self.total_label = ctk.CTkLabel(
            self,
            text="/ 0",
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        self.total_label.grid(row=0, column=2, padx=4, pady=(0, 4), sticky="w")

        # Replay button
        self.replay_button = StandardButton(
            self, text="Replay", command=self._replay, width=80
        )
        self.replay_button.grid(row=0, column=3, padx=(12, 4), pady=(0, 4), sticky="w")

        # Row 1: scrubber aligned to summary/timeline width (synced by TrajectoryViewer)
        self.slider = ctk.CTkSlider(
            self,
            from_=1,
            to=1,
            number_of_steps=1,
            width=280,
            command=self._on_slider_drag,
        )
        self.slider.grid(row=1, column=0, columnspan=4, padx=0, pady=(4, 8), sticky="w")

        # Bind slider release and mouse scroll wheel
        self.slider.bind("<ButtonRelease-1>", lambda e: self._on_slider_release())
        self.slider.bind("<MouseWheel>", self._on_mouse_wheel)
        self.slider.bind("<Button-4>", self._on_mouse_wheel)
        self.slider.bind("<Button-5>", self._on_mouse_wheel)

        # Register callbacks to get notified when stats or new trajectories arrive
        from state_managers import trajectory_stats_state_manager
        trajectory_stats_state_manager.add_on_trajectory_added_callback(
            self.refresh_from_metadata
        )
        trajectory_stats_state_manager.add_on_refresh_stats_callback(
            self.refresh_from_metadata
        )

        # Initial load
        self.refresh_from_metadata()

    def set_slider_width(self, width: int):
        """Match the scrubber width to the summary/timeline column."""
        width = max(160, int(width))
        if int(self.slider.cget("width")) == width:
            return
        self.slider.configure(width=width)

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

        if total > 0:
            if total > 1:
                self.slider.configure(state="normal", from_=1, to=total, number_of_steps=total - 1)
            else:
                self.slider.configure(state="disabled", from_=1, to=1.001, number_of_steps=1)

            # Default to the latest trajectory if none is selected
            if self.current_index is None:
                self.load_trajectory_by_index(total - 1)
            else:
                # Clamp current_index in case the count shrank (unexpected)
                if self.current_index >= total:
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

    def _on_slider_drag(self, value):
        """Updates the text entry in real-time while dragging the slider."""
        self.index_entry.delete(0, "end")
        self.index_entry.insert(0, str(int(value)))

    def _on_slider_release(self):
        """Loads the trajectory only when the slider drag is released."""
        val = int(self.slider.get())
        self.load_trajectory_by_index(val - 1)

    def _on_mouse_wheel(self, event):
        """Permits scrubbing with the mouse wheel on the slider."""
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

        self.slider.set(new_val)
        self._on_slider_drag(new_val)
        self.load_trajectory_by_index(int(new_val) - 1)

    def _on_entry_submit(self):
        """Triggers loading when user presses Enter or focus leaves the Entry field."""
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
            # Revert to the current valid selection if invalid
            val = (self.current_index + 1) if self.current_index is not None else 1

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
        """Synchronizes widgets state to the current_index."""
        total = self.total_trajectories
        if self.current_index is not None and total > 0:
            self.replay_button.configure(state="normal")
            display_val = self.current_index + 1
            self.index_entry.delete(0, "end")
            self.index_entry.insert(0, str(display_val))
            self.slider.set(display_val)
        else:
            self.replay_button.configure(state="disabled")

    def _replay(self):
        """Starts a replay of the currently loaded trajectory."""
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
