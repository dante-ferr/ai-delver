from ._train_process_log import TrainProcessLog


class StaticTrainProcessLog(TrainProcessLog):
    """A CustomTkinter container for displaying static training/play progress."""

    def __init__(self, master, total_steps: int, *, label_prefix: str = "Training levels"):
        super().__init__(master)

        self.total_steps = max(0, int(total_steps))
        self.label_prefix = label_prefix
        self.update_progress(0)

    def update_progress(self, current_step: int):
        current_step = max(0, int(current_step))
        progress = current_step / self.total_steps if self.total_steps > 0 else 0
        self.progress_bar.set(min(1.0, progress))
        self.label.configure(
            text=f"{self.label_prefix}... ({current_step}/{self.total_steps})"
        )
