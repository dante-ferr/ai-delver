from app.components import DeleteButton, FileDeleterOverlay
from level.config import HANDCRAFTED_LEVEL_SAVE_FOLDER_PATH
from app.components.overlay.file_loader_overlay.file_loader_overlay_spawner import (
    FileLoaderOverlaySpawner,
)


class _LevelDeleterOverlay(FileDeleterOverlay):
    def _delete(self, selected_name: str):
        from loaders import level_loader
        from app_manager import app_manager

        was_current = selected_name == level_loader.level.name
        super()._delete(selected_name)

        if was_current:
            level_loader._create_new_level()
            app_manager.editor_app.restart_page("level_editor")


class LevelDeleteButton(DeleteButton):

    def __init__(self, master, **kwargs):
        super().__init__(master, command=self._on_click, **kwargs)

    def _on_click(self):
        FileLoaderOverlaySpawner(
            HANDCRAFTED_LEVEL_SAVE_FOLDER_PATH, "level", _LevelDeleterOverlay
        )
