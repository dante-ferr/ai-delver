import customtkinter as ctk

from app.components import StandardButton
from app.fonts import app_font
from app.components.overlay.checkpoint_restore_overlay import CheckpointRestoreOverlay
from app.components.overlay.message_overlay import MessageOverlay
from loaders import agent_loader
from state_managers import training_state_manager
from src.config import config


class AgentRestoreCheckpointButton(StandardButton):
    """Opens a filterable checkpoint table to restore the current agent's weights."""

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            text="Restore",
            command=self._on_click,
            font=app_font(size=config.STYLE.FONT.STANDARD_SIZE),
            width=72,
            **kwargs,
        )
        training_state_manager.add_disable_on_train_element(self)

    def _on_click(self):
        from cli.commands.checkpoint_store import list_checkpoints

        agent_name = agent_loader.storage_key
        try:
            checkpoints = list_checkpoints(agent_name)
        except Exception as e:
            MessageOverlay(f"Failed to list checkpoints: {e}", subject="Error")
            return

        if not checkpoints:
            MessageOverlay(
                "No checkpoints found for the current agent.",
                subject="Error",
            )
            return

        CheckpointRestoreOverlay(agent_name, checkpoints)
