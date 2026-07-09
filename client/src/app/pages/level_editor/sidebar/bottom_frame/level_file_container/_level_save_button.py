from app.components import SaveButton
from loaders import level_loader
from level.config import LEVEL_SAVE_FOLDER_PATH


class LevelSaveButton(SaveButton):

    def __init__(self, master):
        super().__init__(master, LEVEL_SAVE_FOLDER_PATH, "level")

    def _save(self):
        super()._save()
        level_loader.level.save()

    @property
    def file_name(self) -> str:
        return level_loader.level.name
