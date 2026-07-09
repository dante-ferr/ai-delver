from app.components import FileLoaderOverlay, AddButton
from level.config import LEVEL_SAVE_FOLDER_PATH
from app.components.overlay.file_loader_overlay.file_loader_overlay_spawner import (
    FileLoaderOverlaySpawner,
)
from app.components import MessageOverlay


def training_level_list_component():
    from state_managers import training_state_manager

    if not training_state_manager.training_level_list_component:
        raise Exception("Training level list component not found")

    return training_state_manager.training_level_list_component


class _LevelAdderOverlay(FileLoaderOverlay):
    def __init__(self, file_dirs, file_type):
        super().__init__(
            file_dirs,
            file_type,
            show_sucess_message=False,
        )

    def _load(self):
        super()._load()

        tlc = training_level_list_component()
        tlc.add_box(self.option_menu.get())
        tlc.repack_layout(with_placeholder=False)


class LevelAddButton(AddButton):

    def __init__(self, master, **kwargs):
        super().__init__(master, command=self._on_click, **kwargs)

    def _on_click(self):
        from state_managers import training_state_manager

        max_training_levels = training_state_manager.get_value("max_training_levels")

        if len(training_level_list_component().boxes) >= max_training_levels:
            MessageOverlay(
                "You can't have more than "
                + str(max_training_levels)
                + " training levels.",
                "Error",
            )
            return

        FileLoaderOverlaySpawner(
            LEVEL_SAVE_FOLDER_PATH,
            "level",
            _LevelAdderOverlay,
            exclude_files=training_state_manager.training_levels,
        )
