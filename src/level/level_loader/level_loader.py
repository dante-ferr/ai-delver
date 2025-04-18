from ..level import SAVE_FOLDER_PATH
import dill
from ._level_factory import LevelFactory
from pathlib import Path
from typing import cast, TYPE_CHECKING

if TYPE_CHECKING:
    from ..level import Level

DEFAULT_LEVEL_NAME = "My custom level"
DEFAULT_FILE_PATH = SAVE_FOLDER_PATH / f"{DEFAULT_LEVEL_NAME}.dill"


class LevelLoader:
    def __init__(self):
        self.factory = LevelFactory()
        self._create_new_level()

    def load_level(self, path: str | Path):
        if type(path) == str:
            path = Path(path)
        path = cast(Path, path)

        if path.is_file():
            with open(path, "rb") as file:
                print("Loading existing level")
                self._level = dill.load(file)
            # try:
            #     with open(path, "rb") as file:
            #         self.level = dill.load(file)
            # except Exception as e:
            #     print(f"Error loading instance: {e}. Creating a new one.")
            #     self._create_new_level()
        else:
            print("Creating new level")
            self._create_new_level()

    @property
    def level(self):
        if self._level is None:
            raise ValueError("The level doesn't exist.")
        return self._level

    def _create_new_level(self):
        self._level: "Level" = self.factory.create_level()


level_loader = LevelLoader()
