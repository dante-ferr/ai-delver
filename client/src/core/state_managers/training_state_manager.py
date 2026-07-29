from typing import TYPE_CHECKING, Optional
import customtkinter as ctk
from .state_manager import StateManager

if TYPE_CHECKING:
    import customtkinter as ctk
    from subprocess import Popen
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
        # Owned by TrainButtonsContainer while a CLI train subprocess is alive.
        self.train_process: "Optional[Popen]" = None

        # Set by the UI before training starts.
        self.amount_of_cycles: int = 0
        self.runs_per_cycle: int = 0
        self.checkpoint_interval: int = 5
        # When True, CLI passes --early-stop so levels advance on policy convergence.
        self.early_stop: bool = False
        # True while a Play Levels session is active (vs Train).
        self.play_session: bool = False

        # Real-time deep learning metrics accumulated during training
        self.nerd_loss_history: list[float] = []
        self.nerd_return_history: list[float] = []
        self.nerd_step_history: list[int] = []

        # All-time historical metrics loaded from metadata
        self.all_time_loss_history: list[float] = []
        self.all_time_return_history: list[float] = []
        self.all_time_step_history: list[int] = []

        self._nerd_stats_listeners: list[callable] = []

        self.add_variable(
            "connected_to_server", ctk.StringVar, "no"
        )  # no, yes, loading
        self.add_variable("env_batch_size", ctk.IntVar, 32)
        self.add_variable("max_training_levels", ctk.IntVar, 1)
        self.add_variable("levels_trained", ctk.IntVar, 0)
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
            self.train_logs_panel.update_training_progress(current_cycle)

    def set_training_process_log_total(self, total_steps: int, progress_base: int = 0):
        if self.train_logs_panel:
            self.train_logs_panel.set_training_progress_total(
                total_steps, progress_base=progress_base
            )

    def show_review_process_log(self, total_steps: int):
        if self.train_logs_panel:
            self.train_logs_panel.show_review_progress(total_steps)

    def update_review_process_log(self, current_cycle: int):
        if self.train_logs_panel:
            self.train_logs_panel.update_review_progress(current_cycle)

    def remove_review_process_log(self):
        if self.train_logs_panel:
            self.train_logs_panel.remove_review_progress()


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
        stale_disabled = set()
        for element in list(self.disable_on_train_elements):
            try:
                if hasattr(element, "winfo_exists") and not element.winfo_exists():
                    stale_disabled.add(element)
                    continue
                element.configure(state=state_for_disable_elements)
            except Exception:
                stale_disabled.add(element)
        self.disable_on_train_elements.difference_update(stale_disabled)

        state_for_enable_elements = (
            "normal" if is_training_and_not_interrupting else "disabled"
        )
        stale_enabled = set()
        for element in list(self.enable_on_train_elements):
            try:
                if hasattr(element, "winfo_exists") and not element.winfo_exists():
                    stale_enabled.add(element)
                    continue
                element.configure(state=state_for_enable_elements)
            except Exception:
                stale_enabled.add(element)
        self.enable_on_train_elements.difference_update(stale_enabled)

        if self.train_logs_panel:
            try:
                if hasattr(self.train_logs_panel, "winfo_exists") and not self.train_logs_panel.winfo_exists():
                    self.train_logs_panel = None
            except Exception:
                self.train_logs_panel = None

        if self.train_logs_panel:
            if self.get_value("sending_training_request"):
                request_text = (
                    "Sending play request..."
                    if self.play_session
                    else "Sending training request..."
                )
                self.train_logs_panel.show_log("sending_request", request_text)
            else:
                self.train_logs_panel.remove_log("sending_request")

            if self.get_value("training"):
                self.train_logs_panel.show_training_progress()
            else:
                self.train_logs_panel.remove_training_progress()

            if self.get_value("sending_interrupt_training_request"):
                interrupt_text = (
                    "Interrupting play..."
                    if self.play_session
                    else "Interrupting training..."
                )
                self.train_logs_panel.show_log("interrupting", interrupt_text)
            else:
                self.train_logs_panel.remove_log("interrupting")

    def reset_states(self):
        """Resets all state flags to their initial (idle) values and updates the UI."""
        self.play_session = False
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

    # ------------------------------------------------------------------
    # Nerd Stats (deep learning metrics streamed during training)
    # ------------------------------------------------------------------

    def register_nerd_stats_listener(self, callback: callable):
        """Registers a callback to receive real-time nerd metric updates."""
        self._nerd_stats_listeners.append(callback)

    def unregister_nerd_stats_listener(self, callback: callable):
        """Removes a previously registered nerd stats listener."""
        try:
            self._nerd_stats_listeners.remove(callback)
        except ValueError:
            pass

    def update_nerd_metrics(self, step, loss, average_return, episodes):
        """
        Receives a new metrics snapshot from the training subprocess and
        appends it to the histories, then notifies all registered listeners.
        Called from the background thread reading the CLI subprocess stdout.
        """
        if step is None:
            return
        self.nerd_loss_history.append(loss if loss is not None else 0.0)
        self.nerd_return_history.append(average_return if average_return is not None else 0.0)
        self.nerd_step_history.append(step)

        # Also append to the all-time history so that the all-time chart updates live during training
        self.all_time_loss_history.append(loss if loss is not None else 0.0)
        self.all_time_return_history.append(average_return if average_return is not None else 0.0)
        self.all_time_step_history.append(step)

        for cb in list(self._nerd_stats_listeners):
            try:
                cb(self.nerd_step_history, self.nerd_loss_history, self.nerd_return_history)
            except Exception as e:
                print(f"[NerdStats] Listener error: {e}")

    def clear_nerd_metrics(self):
        """Clears all accumulated nerd metrics (called at training start)."""
        self.nerd_loss_history.clear()
        self.nerd_return_history.clear()
        self.nerd_step_history.clear()


training_state_manager = TrainingStateManager()
