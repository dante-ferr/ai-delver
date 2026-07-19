import customtkinter as ctk
from app.components import RangeSliderInput
from typing import Callable
from state_managers import training_state_manager


class EpisodesSettingPanel(ctk.CTkFrame):
    """Training budget controls. Users pick full-length runs; intelligence converts to episode slots."""

    MAX_RUNS_PER_CYCLE = 100

    def __init__(
        self,
        master,
        on_amount_of_runs_change: Callable,
    ):
        super().__init__(master, fg_color="transparent")

        self.on_amount_of_runs_change = on_amount_of_runs_change

        init_val = 10
        self.training_cycles_input = RangeSliderInput(
            self,
            label_text="Training Cycles",
            min_val=1,
            max_val=100,
            init_val=init_val,
            step=1,
            on_update=self._set_training_cycles,
            fg_color="transparent",
        )
        self.training_cycles_input.pack(pady=(0, 16), fill="x")
        training_state_manager.amount_of_cycles = init_val

        init_runs = 5
        self.runs_per_cycle_input = RangeSliderInput(
            self,
            label_text="Runs per Cycle",
            min_val=1,
            max_val=self.MAX_RUNS_PER_CYCLE,
            init_val=init_runs,
            step=1,
            on_update=self._set_runs_per_cycle,
            fg_color="transparent",
        )
        self.runs_per_cycle_input.pack(pady=(0, 16), fill="x")
        training_state_manager.runs_per_cycle = init_runs

        init_checkpoint = 5
        self.checkpoint_interval_input = RangeSliderInput(
            self,
            label_text="Checkpoint every N cycles",
            min_val=1,
            max_val=100,
            init_val=init_checkpoint,
            step=1,
            on_update=self._set_checkpoint_interval,
            fg_color="transparent",
        )
        self.checkpoint_interval_input.pack(pady=0, fill="x")
        training_state_manager.checkpoint_interval = init_checkpoint

    def _set_training_cycles(self, value):
        training_state_manager.amount_of_cycles = value
        self.on_amount_of_runs_change()

    def _set_runs_per_cycle(self, value):
        training_state_manager.runs_per_cycle = value
        self.on_amount_of_runs_change()

    def _set_checkpoint_interval(self, value):
        training_state_manager.checkpoint_interval = int(value)
