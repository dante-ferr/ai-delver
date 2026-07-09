from src.app.components import LoadingLogsPanel
from .train_process_log import StaticTrainProcessLog
from .train_process_log import DynamicTrainProcessLog
from state_managers import training_state_manager


class TrainLogsPanel(LoadingLogsPanel):

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        self.training_progress_log: (
            StaticTrainProcessLog | DynamicTrainProcessLog | None
        ) = None
        self.showing_training_progress = False

        training_state_manager.set_train_logs_panel(self)

    def show_training_progress(self):
        if self.showing_training_progress:
            return
        self.showing_training_progress = True

        if training_state_manager.get_value("level_transitioning_mode") == "dynamic":
            self.training_progress_log = DynamicTrainProcessLog(self)
        else:
            self.training_progress_log = StaticTrainProcessLog(
                self, training_state_manager.total_amount_of_cycles
            )

        self.training_progress_log.pack(fill="x", expand=True)

    def update_training_progress(self, current_value: int):
        if self.training_progress_log:
            self.training_progress_log.update_progress(current_value)

    def remove_training_progress(self):
        if not self.showing_training_progress:
            return
        self.showing_training_progress = False

        if self.training_progress_log:
            self.training_progress_log.destroy()
            self.training_progress_log = None
