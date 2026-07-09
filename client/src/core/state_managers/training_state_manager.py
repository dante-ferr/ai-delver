from typing import TYPE_CHECKING
import customtkinter as ctk
from .state_manager import StateManager

if TYPE_CHECKING:
    import customtkinter as ctk
    from app.pages.agent.train_panel._train_logs_panel import TrainLogsPanel
    from app.pages.agent.train_panel.level_selector._level_list import (
        LevelList as TrainingLevelList,
    )


class TrainingStateManager(StateManager):
    """
    Manages the global state related to the agent training process.

    This includes tracking whether a training request is in flight, if training is
    active, or if an interruption has been requested. It also holds references to UI
    elements to automatically update their state (e.g., enabled/disabled).
    """
    def __init__(self):
        super().__init__()

        self.disable_on_train_elements: "set[ctk.CTkBaseClass]" = set()
        self.enable_on_train_elements: "set[ctk.CTkBaseClass]" = set()
        self.train_logs_panel: "TrainLogsPanel | None" = None
        self.training_level_list_component: "TrainingLevelList | None" = None

        # Set by the UI before training starts.
        self.amount_of_cycles: int = 0
        self.episodes_per_cycle: int = 0

        self.add_variable(
            "connected_to_server", ctk.StringVar, "no"
        )  # no, yes, loading
        self.add_variable("env_batch_size", ctk.IntVar, 32)
        self.add_variable("max_training_levels", ctk.IntVar, 1)
        self.add_variable("levels_trained", ctk.IntVar, 0)
        self.add_variable("level_transitioning_mode", ctk.StringVar, "static")
        self.add_variable("level_episode_count", ctk.IntVar, 0)
        self.add_variable("sending_training_request", ctk.BooleanVar, False)
        self.add_variable("training", ctk.BooleanVar, False)
        self.add_variable("sending_interrupt_training_request", ctk.BooleanVar, False)

        # Register callbacks to update UI when these change.
        # We use a lambda to discard the value argument since _update_ui_state reads all.
        # Note: add_callback calls the callback immediately, so UI state is initialized here.
        self.add_callback("sending_training_request", lambda _: self._update_ui_state())
        self.add_callback("training", lambda _: self._update_ui_state())
        self.add_callback(
            "sending_interrupt_training_request", lambda _: self._update_ui_state()
        )

    @property
    def total_amount_of_cycles(self) -> int:
        return self.amount_of_cycles * len(self.training_levels)

    @property
    def training_levels(self) -> list[str]:
        if self.training_level_list_component is None:
            return []

        return self.training_level_list_component.get_order()

    def set_train_logs_panel(self, panel: "TrainLogsPanel"):
        self.train_logs_panel = panel
        self._update_ui_state()

    def add_disable_on_train_element(self, element: "ctk.CTkBaseClass"):
        self.disable_on_train_elements.add(element)
        self._update_ui_state()

    def add_enable_on_train_element(self, element: "ctk.CTkBaseClass"):
        self.enable_on_train_elements.add(element)
        self._update_ui_state()

    def update_training_process_log(self, current_cycle: int):
        if self.train_logs_panel:
            if self.get_value("level_transitioning_mode") == "dynamic":
                self.train_logs_panel.update_training_progress(
                    self.get_value("levels_trained")
                )
            else:
                self.train_logs_panel.update_training_progress(current_cycle)

    def _update_ui_state(self):
        """
        Updates the state of all registered UI elements based on the current
        training state flags. This is the central method for ensuring UI
        consistency during the training lifecycle.
        """
        is_busy = (
            self.get_value("sending_training_request")
            or self.get_value("training")
            or self.get_value("sending_interrupt_training_request")
        )
        is_training_and_not_interrupting = self.get_value(
            "training"
        ) and not self.get_value("sending_interrupt_training_request")

        state_for_disable_elements = "disabled" if is_busy else "normal"
        for element in self.disable_on_train_elements:
            element.configure(state=state_for_disable_elements)

        state_for_enable_elements = (
            "normal" if is_training_and_not_interrupting else "disabled"
        )
        for element in self.enable_on_train_elements:
            element.configure(state=state_for_enable_elements)

        if self.train_logs_panel:
            if self.get_value("sending_training_request"):
                self.train_logs_panel.show_log(
                    "sending_request", "Sending training request..."
                )
            else:
                self.train_logs_panel.remove_log("sending_request")

            if self.get_value("training"):
                self.train_logs_panel.show_training_progress()
            else:
                self.train_logs_panel.remove_training_progress()

            if self.get_value("sending_interrupt_training_request"):
                self.train_logs_panel.show_log(
                    "interrupting", "Interrupting training..."
                )
            else:
                self.train_logs_panel.remove_log("interrupting")

    def reset_states(self):
        """Resets all state flags to their initial (idle) values and updates the UI."""
        self.set_value("sending_training_request", False)
        self.set_value("training", False)
        self.set_value("sending_interrupt_training_request", False)

    @property
    def sending_training_request(self):
        return self.get_value("sending_training_request")

    @sending_training_request.setter
    def sending_training_request(self, value: bool):
        if self.get_value("sending_training_request") == value:
            return
        self.set_value("sending_training_request", value)

    @property
    def training(self):
        return self.get_value("training")

    @training.setter
    def training(self, value: bool):
        if self.get_value("training") == value:
            return
        self.set_value("training", value)

    @property
    def sending_interrupt_training_request(self):
        return self.get_value("sending_interrupt_training_request")

    @sending_interrupt_training_request.setter
    def sending_interrupt_training_request(self, value: bool):
        if self.get_value("sending_interrupt_training_request") == value:
            return
        self.set_value("sending_interrupt_training_request", value)


training_state_manager = TrainingStateManager()
