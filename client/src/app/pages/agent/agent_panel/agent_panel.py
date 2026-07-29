import customtkinter as ctk
from ._agent_title_textbox import AgentTitleTextbox
from .agent_file_container import AgentFileContainer
from .trajectory_stats_panel import TrajectoryStatsPanel
from app.components import AnimatedGifLabel
from src.config import config
from state_managers import training_state_manager


class AgentPanel(ctk.CTkFrame):
    EPISODES_BATCH = 20
    """
    A CustomTkinter panel for creating, editing, saving, and loading Agents.
    """

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        title_textbox = AgentTitleTextbox(self)
        title_textbox.pack(padx=0, pady=(0, config.STYLE.SECTION_SPACING), fill="x")

        trajectory_stats_panel = TrajectoryStatsPanel(self)
        trajectory_stats_panel.pack(
            padx=0, pady=(0, config.STYLE.SECTION_SPACING), fill="x"
        )

        self.gif_label = AnimatedGifLabel(self)
        self.gif_label.pack(pady=(0, config.STYLE.SECTION_SPACING))

        training_state_manager.add_callback(
            "training", self._on_training_state_changed
        )

        agent_file_container = AgentFileContainer(self)
        agent_file_container.pack(side="bottom", padx=2, pady=2)

    def _on_training_state_changed(self, is_training: bool):
        if is_training:
            self.gif_label.load_gif_by_name("run")
        else:
            self.gif_label.load_gif_by_name("idle")
