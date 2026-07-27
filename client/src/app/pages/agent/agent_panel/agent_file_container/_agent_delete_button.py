from pathlib import Path

from app.components import DeleteButton, FileDeleterOverlay
from agent.config import AGENT_SAVE_FOLDER_PATH, SESSION_STORAGE_KEY
from agent.session_workspace import reset_session_workspace
from app.components.overlay.file_loader_overlay.file_loader_overlay_spawner import (
    FileLoaderOverlaySpawner,
)
from state_managers import training_state_manager


class _AgentDeleterOverlay(FileDeleterOverlay):
    def _delete(self, selected_name: str):
        from loaders import agent_loader
        from app_manager import app_manager

        was_current = (
            selected_name == agent_loader.agent.name
            or selected_name == agent_loader.bound_name
        )
        super()._delete(selected_name)

        # Only reset the live session if the named save actually went away.
        deleted = not (Path(AGENT_SAVE_FOLDER_PATH) / selected_name).exists()
        if was_current and deleted:
            # Named save is gone; wipe live session so the UI is a blank Delver.
            reset_session_workspace()
            agent_loader._create_new_agent()
            training_state_manager.clear_nerd_metrics()
            training_state_manager.all_time_loss_history = []
            training_state_manager.all_time_return_history = []
            training_state_manager.all_time_step_history = []
            app_manager.editor_app.restart_all_pages()


class AgentDeleteButton(DeleteButton):

    def __init__(self, master, **kwargs):
        super().__init__(master, command=self._on_click, **kwargs)
        training_state_manager.add_disable_on_train_element(self)

    def _on_click(self):
        FileLoaderOverlaySpawner(
            AGENT_SAVE_FOLDER_PATH,
            "agent",
            _AgentDeleterOverlay,
            exclude_files=[SESSION_STORAGE_KEY],
        )
