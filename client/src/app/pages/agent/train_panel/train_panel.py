import customtkinter as ctk
from ._train_logs_panel import TrainLogsPanel
from ._train_buttons_container import TrainButtonsContainer
from src.config import config
from .level_selector import LevelSelector
from ._episodes_setting_panel import EpisodesSettingPanel
from app.components import AnimatedGifLabel
from app.fonts import app_font
from state_managers import training_state_manager


class TrainPanel(ctk.CTkFrame):
    """
    A CustomTkinter panel for creating, editing, saving, and loading Agents.
    """

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        train_buttons_container = TrainButtonsContainer(self)
        train_buttons_container.pack(
            padx=2, pady=(0, 16), fill="x"
        )

        self.level_selector = LevelSelector(
            self, on_amount_of_runs_change=self._set_amount_of_runs
        )

        self.episodes_setting_panel = EpisodesSettingPanel(
            self,
            on_amount_of_runs_change=self._set_amount_of_runs,
        )
        self.episodes_setting_panel.pack(pady=(0, 12), fill="x")

        self.info_frame = ctk.CTkFrame(self, fg_color="transparent", width=0, height=0)
        self.info_frame.pack(fill="x", pady=(0, 12))

        self.cycles_label = ctk.CTkLabel(
            self.info_frame,
            text="",
            font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        self.cycles_label.pack(anchor="w")

        self.runs_label = ctk.CTkLabel(
            self.info_frame,
            text="",
            font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        self.runs_label.pack(anchor="w")

        self.level_selector.pack(
            pady=(12, 12), fill="x"
        )

        # Logs panel at the bottom taking full width
        bottom_container = ctk.CTkFrame(self, fg_color="transparent")
        bottom_container.pack(
            fill="both", expand=True, pady=(0, 8)
        )

        train_logs_panel = TrainLogsPanel(bottom_container)
        train_logs_panel.pack(fill="both", expand=True, padx=2)

        self._set_amount_of_runs()


    def _set_amount_of_runs(self):
        if not hasattr(self, "level_selector") or not hasattr(self, "episodes_setting_panel"):
            return

        amount_of_levels = len(self.level_selector.level_list.get_order())

        cycles_per_level = int(self.episodes_setting_panel.training_cycles_input.get())
        total_cycles = cycles_per_level * amount_of_levels

        self.cycles_label.configure(
            text=f"{cycles_per_level} cycles per level (total: {total_cycles})"
        )

        runs_per_level = int(
            cycles_per_level
            * self.episodes_setting_panel.runs_per_cycle_input.get()
        )
        total_runs = runs_per_level * amount_of_levels

        self.runs_label.configure(
            text=f"{runs_per_level} runs per level (total: {total_runs})"
        )
