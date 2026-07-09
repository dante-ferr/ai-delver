import customtkinter as ctk
from ._agent_title_textbox import AgentTitleTextbox
from .agent_file_container import AgentFileContainer
from .trajectory_stats_panel import TrajectoryStatsPanel
from src.config import config

class AgentPanel(ctk.CTkFrame):
    EPISODES_BATCH = 20
    """
    A CustomTkinter panel for creating, editing, saving, and loading Agents.
    """

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        title_textbox = AgentTitleTextbox(self)
        title_textbox.pack(padx=0, pady=(0, config.STYLE.SECTION_SPACING), fill="x")

        agent_file_container = AgentFileContainer(self)
        agent_file_container.pack(side="bottom", padx=2, pady=2)

        trajectory_stats_panel = TrajectoryStatsPanel(self)
        trajectory_stats_panel.pack(
            padx=0, pady=(0, config.STYLE.SECTION_SPACING), fill="x"
        )
