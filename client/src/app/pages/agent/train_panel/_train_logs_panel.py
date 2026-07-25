from src.app.components import LoadingLogsPanel
from .train_process_log import StaticTrainProcessLog
from state_managers import training_state_manager


class TrainLogsPanel(LoadingLogsPanel):

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        self.training_progress_log: StaticTrainProcessLog | None = None
        self.review_progress_log: StaticTrainProcessLog | None = None
        self.showing_training_progress = False
        self.showing_review_progress = False
        self._review_total_steps = 0

        training_state_manager.set_train_logs_panel(self)

    def show_training_progress(self):
        if self.showing_training_progress:
            return
        self.showing_training_progress = True

        if training_state_manager.play_session:
            total_steps = len(training_state_manager.training_levels)
            label_prefix = "Playing levels"
        else:
            total_steps = training_state_manager.total_amount_of_cycles
            label_prefix = "Training levels"

        self.training_progress_log = StaticTrainProcessLog(
            self, total_steps, label_prefix=label_prefix
        )

        self.training_progress_log.pack(fill="x", expand=True)

    def update_training_progress(self, current_value: int):
        if self.training_progress_log:
            self.training_progress_log.update_progress(current_value)

    def set_training_progress_total(self, total_steps: int, progress_base: int = 0):
        """Resize the focus bar when a chained focus phase starts.

        ``progress_base`` keeps cumulative progress across sequential per-level
        focus sessions (n cycles each) instead of resetting to 0 every level.
        """
        total_steps = max(1, int(total_steps))
        progress_base = max(0, int(progress_base or 0))
        if self.training_progress_log is None:
            self.show_training_progress()
        if self.training_progress_log is not None:
            self.training_progress_log.total_steps = total_steps
            self.training_progress_log.update_progress(progress_base)

    def show_review_progress(self, total_steps: int):
        total_steps = max(1, int(total_steps))
        self._review_total_steps = total_steps
        if self.review_progress_log is not None:
            self.review_progress_log.total_steps = total_steps
            self.review_progress_log.update_progress(0)
            return

        self.showing_review_progress = True
        self.review_progress_log = StaticTrainProcessLog(
            self, total_steps, label_prefix="Reviewing levels"
        )
        self.review_progress_log.pack(fill="x", expand=True, pady=(8, 0))

    def update_review_progress(self, current_value: int):
        if self.review_progress_log:
            self.review_progress_log.update_progress(current_value)

    def remove_review_progress(self):
        if not self.showing_review_progress and self.review_progress_log is None:
            return
        self.showing_review_progress = False
        if self.review_progress_log:
            self.review_progress_log.destroy()
            self.review_progress_log = None
        self._review_total_steps = 0

    def remove_training_progress(self):
        if not self.showing_training_progress:
            self.remove_review_progress()
            return
        self.showing_training_progress = False

        if self.training_progress_log:
            self.training_progress_log.destroy()
            self.training_progress_log = None
        self.remove_review_progress()
