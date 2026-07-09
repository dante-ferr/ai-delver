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

        self.index_entry = ctk.CTkEntry(
            self,
            placeholder_text="Trajectory Index",
            width=128,
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        self.index_entry.grid(row=0, column=0, padx=4, pady=(0, 4))

        load_button = StandardButton(
            self, text="Load", command=self._load_trajectory, width=128
        )
        load_button.grid(row=0, column=1, padx=4, pady=(0, 4))

        replay_button = StandardButton(
            self, text="Replay", command=lambda: self._replay()
        )
        replay_button.grid(row=0, column=2, padx=4, pady=(0, 4))

    def _load_trajectory(self):
        """Loads a trajectory by the index specified in the entry field."""
        self.master = cast("TrajectoryViewer", self.master)

        index_str = self.index_entry.get()
        if not index_str:
            MessageOverlay("Please enter a trajectory index.", subject="Error")
            return

        try:
            index = int(index_str)
        except ValueError:
            MessageOverlay("Index must be an integer.", subject="Error")
            return

        trajectory = self.trajectory_loader.load_trajectory(index)
        if trajectory is None:
            MessageOverlay(
                f"Trajectory with index '{index}' not found. See the amount of trajectories your agent have trained on in the Stats panel.",
                subject="Error",
            )
            return

        self.master.trajectory = trajectory
        self.master.display_trajectory()

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
