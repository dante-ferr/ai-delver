from ._level_factory import LevelFactory
from pathlib import Path
from level import config as level_config
from typing import Callable, cast, TYPE_CHECKING

if TYPE_CHECKING:
    from ..level import Level


class LevelLoader:

    def __init__(self):
        self.factory = LevelFactory()
        self._dirty: bool = False
        self._dirty_listeners: list[Callable[[bool], None]] = []
        self._create_new_level()

    def load_level(
        self,
        dir_path: str | Path = level_config.LEVEL_SAVE_FOLDER_PATH,
        file_name: str = "level.json",
    ):
        """Loads a level from a file. The path of the level directory must be provided (instead of the level file itself)."""
        if type(dir_path) == str:
            dir_path = Path(dir_path)
        dir_path = cast(Path, dir_path)
        file_path = dir_path / file_name

        if file_path.is_file():
            from ..level import Level

            return Level.load(str(file_path))
        else:
            from ..exceptions import LevelLoadError
            raise LevelLoadError(str(file_path), "File not found.")

    @property
    def level(self):
        if self._level is None:
            from ..exceptions import LevelLoadError
            raise LevelLoadError("", "The level has not been loaded or created.")
        return self._level

    @level.setter
    def level(self, value: "Level"):
        """Sets the level to the given level."""
        self._level = value

    @property
    def dirty(self) -> bool:
        return self._dirty

    def mark_dirty(self) -> None:
        self._set_dirty(True)

    def mark_saved(self) -> None:
        self._set_dirty(False)

    def add_dirty_listener(self, callback: Callable[[bool], None]) -> None:
        self._dirty_listeners.append(callback)

    def remove_dirty_listener(self, callback: Callable[[bool], None]) -> None:
        if callback in self._dirty_listeners:
            self._dirty_listeners.remove(callback)

    def _create_new_level(self):
        self._level: "Level" = self.factory.create_level()
        self._set_dirty(False)

    def _set_dirty(self, dirty: bool) -> None:
        dirty = bool(dirty)
        if dirty == self._dirty:
            return
        self._dirty = dirty
        for listener in list(self._dirty_listeners):
            listener(dirty)
