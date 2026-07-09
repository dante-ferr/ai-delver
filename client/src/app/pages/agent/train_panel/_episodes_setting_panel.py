import customtkinter as ctk
from app.components import RangeSliderInput
from typing import Callable
from state_managers import training_state_manager
from src.config import config

class EpisodesSettingPanel(ctk.CTkFrame):
    MAX_ENV_BATCHES_PER_CYCLE = 20

    def __init__(
        self,
        master,
        on_amount_of_episodes_change: Callable,
    ):
        super().__init__(master, fg_color="transparent")

        self.on_amount_of_episodes_change = on_amount_of_episodes_change

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

        init_val = 50
        self.episodes_per_cycle_input = RangeSliderInput(
            self,
            label_text="Episodes per Cycle",
            on_update=self._set_episodes_per_cycle,
            fg_color="transparent",
        )
        self.episodes_per_cycle_input.pack(pady=0, fill="x")
        training_state_manager.episodes_per_cycle = init_val

        training_state_manager.add_callback(
            "env_batch_size", self._on_env_batch_size_update
        )
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
                pady=(0, 16), fill="x", before=self.episodes_per_cycle_input
            )

    def _set_training_cycles(self, value):
        training_state_manager.amount_of_cycles = value
        self.on_amount_of_episodes_change()

    def _set_episodes_per_cycle(self, value):
        training_state_manager.episodes_per_cycle = value
        self.on_amount_of_episodes_change()

    def _on_env_batch_size_update(self, value):
        self.episodes_per_cycle_input.configure(
            min_val=value, step=value, max_val=self.MAX_ENV_BATCHES_PER_CYCLE * value
        )
        self.episodes_per_cycle_input.set_value(value)
