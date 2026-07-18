import customtkinter as ctk
from app.components import RangeSliderInput
from typing import Callable
from state_managers import training_state_manager
from src.config import config

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

        self.transition_label = ctk.CTkLabel(
            self,
            text="Level Transitioning",
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE, weight="bold"),
        )
        self.transition_label.pack(anchor="w")
        self.transition_mode_input = ctk.CTkSegmentedButton(
            self,
            values=["static", "dynamic"],
            command=self._on_transition_mode_update,
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        self.transition_mode_input.set("static")
        self.transition_mode_input.pack(pady=(0, 16), fill="x")

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
        self.runs_per_cycle_input.pack(pady=0, fill="x")
        training_state_manager.runs_per_cycle = init_runs

        training_state_manager.add_callback(
            "level_transitioning_mode", self._update_visibility
        )

    def _on_transition_mode_update(self, value: str):
        training_state_manager.set_value("level_transitioning_mode", value.lower())

    def _update_visibility(self, value):
        if value == "dynamic":
            self.training_cycles_input.pack_forget()
        else:
            self.training_cycles_input.pack(
                pady=(0, 16), fill="x", before=self.runs_per_cycle_input
            )

    def _set_training_cycles(self, value):
        training_state_manager.amount_of_cycles = value
        self.on_amount_of_runs_change()

    def _set_runs_per_cycle(self, value):
        training_state_manager.runs_per_cycle = value
        self.on_amount_of_runs_change()
