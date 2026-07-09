from ._train_process_log import TrainProcessLog


class StaticTrainProcessLog(TrainProcessLog):
    """A CustomTkinter container for displaying static training progress."""

    def __init__(self, master, total_cycles: int):
        super().__init__(master)

        self.total_cycles = total_cycles
        self.update_progress(0)

    def update_progress(self, current_step: int):
        progress = current_step / self.total_cycles if self.total_cycles > 0 else 0
        self.progress_bar.set(progress)
        self.label.configure(
            text=f"Training in progress... ({current_step}/{int(self.total_cycles)})"
        )
