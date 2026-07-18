from app.components import DeleteButton, FileDeleterOverlay
from agent.config import AGENT_SAVE_FOLDER_PATH
from app.components.overlay.file_loader_overlay.file_loader_overlay_spawner import (
    FileLoaderOverlaySpawner,
)


class _AgentDeleterOverlay(FileDeleterOverlay):
    def _delete(self, selected_name: str):
        from loaders import agent_loader
        from app_manager import app_manager

        was_current = selected_name == agent_loader.agent.name
        super()._delete(selected_name)

        if was_current:
            agent_loader._create_new_agent()
            app_manager.editor_app.restart_all_pages()


class AgentDeleteButton(DeleteButton):

    def __init__(self, master, **kwargs):
        super().__init__(master, command=self._on_click, **kwargs)

    def _on_click(self):
        FileLoaderOverlaySpawner(AGENT_SAVE_FOLDER_PATH, "agent", _AgentDeleterOverlay)
