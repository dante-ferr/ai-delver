import customtkinter as ctk
import json
from app.components.overlay.message_overlay import MessageOverlay
from typing import TYPE_CHECKING
from ._header import TrajectoryHeader

if TYPE_CHECKING:
    from runtime.episode_trajectory import EpisodeTrajectory


class TrajectoryViewer(ctk.CTkFrame):
    DISPLAY_TRAJECTORY_JSON = True

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = TrajectoryHeader(self)
        header.grid(row=0, column=0, padx=8, pady=(0, 4), sticky="w")

        self.data_display = ctk.CTkTextbox(self, wrap="none")
        self.data_display.grid(row=1, column=0, padx=8, pady=(4, 8), sticky="nsew")
        self._set_data_display_to_default()
        self.data_display.configure(state="disabled")

        self.trajectory: "EpisodeTrajectory | None" = None

    def display_trajectory(self):
        if self.DISPLAY_TRAJECTORY_JSON:
            self._display_trajectory_json()
        else:
            self._display_trajectory_data()

    def _display_trajectory_json(self):
        if self.trajectory is None:
            raise ValueError("Trajectory is not loaded.")
        trajectory_json_str = self.trajectory.to_json()

        self.data_display.configure(state="normal")
        self.data_display.delete("1.0", "end")

        try:
            parsed_json = json.loads(trajectory_json_str)
            formatted_json = json.dumps(parsed_json, indent=4)
            self.data_display.insert("1.0", formatted_json)
        except json.JSONDecodeError:
            MessageOverlay(f"Error decoding trajectory data.", subject="Error")
            self.data_display.insert("1.0", "Failed to load trajectory data.")

        self.data_display.configure(state="disabled")

    def _set_data_display_to_default(self):
        self.data_display.insert(
            "1.0",
            "Trajectory data will be shown here. Make sure to train the agent before searching for a trajectory.",
        )

    def _display_trajectory_data(self):
        pass
