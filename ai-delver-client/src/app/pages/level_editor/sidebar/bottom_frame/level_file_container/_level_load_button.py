from app.components import FileLoaderOverlay, LoadButton
from level.config import LEVEL_SAVE_FOLDER_PATH
from app.components.overlay.file_loader_overlay.file_loader_overlay_spawner import (
    FileLoaderOverlaySpawner,
)


class _LevelLoaderOverlay(FileLoaderOverlay):
    def _load(self):
        from loaders import level_loader
        from app_manager import app_manager

        super()._load()
        level = level_loader.load_level(self._get_file_path())
        if level is None:
            raise RuntimeError("Failed to load level")
        level_loader.level = level
        app_manager.editor_app.restart_all_pages()


class LevelLoadButton(LoadButton):

    def __init__(self, master, **kwargs):
        super().__init__(master, command=self._on_click, **kwargs)

    def _on_click(self):
        FileLoaderOverlaySpawner(LEVEL_SAVE_FOLDER_PATH, "level", _LevelLoaderOverlay)
