from ._train_process_log import TrainProcessLog
from state_managers import training_state_manager
from src.config import config
import customtkinter as ctk


class DynamicTrainProcessLog(TrainProcessLog):
    """A CustomTkinter container for displaying dynamic training progress."""

    def __init__(self, master):
        super().__init__(master)
        self.total_levels = len(training_state_manager.training_levels)

        self.update_progress(0)

        self.level_episode_count_label = ctk.CTkLabel(
            self, font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE), text=""
        )
        self.level_episode_count_label.pack()

        training_state_manager.add_callback(
            "level_episode_count", self.update_level_episode_count
        )

    def update_progress(self, current_step: int):
        progress = current_step / self.total_levels if self.total_levels > 0 else 0
        self.progress_bar.set(progress)
        self.label.configure(
            text=f"Training in progress... ({current_step}/{self.total_levels})"
        )

    def update_level_episode_count(self, _):
        self.level_episode_count_label.configure(
            text=f"Amount of training episodes in the current level: {training_state_manager.get_value("level_episode_count")}"
        )
