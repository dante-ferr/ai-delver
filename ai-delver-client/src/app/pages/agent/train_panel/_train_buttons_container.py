import customtkinter as ctk
from state_managers import training_state_manager
import asyncio
from app.utils import verify_level_issues
from client_requests import client_requester
import threading
from app.components import StandardButton


class TrainButtonsContainer(ctk.CTkFrame):
    """
    A UI container with buttons to start and interrupt agent training.
    It handles running the asynchronous training requests in a separate thread
    to prevent blocking the main GUI thread.
    """

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.train_button = StandardButton(
            self, text="Train", command=self._start_train_thread
        )
        self.train_button.grid(row=0, column=0, padx=(0, 4))

        self.interrupt_training_button = StandardButton(
            self,
            text="Interrupt Training",
            command=self._start_interrupt_thread,
        )
        self.interrupt_training_button.grid(row=0, column=1, padx=(4, 0))

        training_state_manager.add_disable_on_train_element(self.train_button)
        training_state_manager.add_enable_on_train_element(
            self.interrupt_training_button
        )

    def _start_train_thread(self):
        """
        Starts the training request in a new thread to avoid blocking the GUI.
        """
        thread = threading.Thread(
            target=lambda: asyncio.run(self._train()), daemon=True
        )
        thread.start()

    def _start_interrupt_thread(self):
        """
        Starts the interrupt request in a new thread to avoid blocking the GUI.
        """
        thread = threading.Thread(
            target=lambda: asyncio.run(self._interrupt_training()), daemon=True
        )
        thread.start()

    async def _train(self):
        if not verify_level_issues():
            # This coroutine runs in a new event loop within a background thread,
            # initiated by _start_train_thread.
            await client_requester.send_training_request()

    async def _interrupt_training(self):
        """Wrapper for the interrupt request coroutine."""
        # This coroutine runs in a new event loop within a background thread,
        # initiated by _start_interrupt_thread.
        await client_requester.send_interrupt_training_request()
