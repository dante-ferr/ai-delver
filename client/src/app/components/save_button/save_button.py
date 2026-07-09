from pathlib import Path
from app.components import IconButton
from src.config import config
from app.components.overlay.message_overlay import MessageOverlay


class SaveButton(IconButton):
    """
    A base class for save buttons that handles saving files with an overwrite
    confirmation dialog.

    This class cannot be used directly and must be subclassed. Subclasses must
    implement the `file_name` property and can override the `_save` method.
    """

    def __init__(self, master, save_folder_path: str, file_type: str, **kwargs):
        super().__init__(
            master,
            svg_path=str(config.ASSETS_PATH / "svg" / "save.svg"),
            command=self._on_click,
            **kwargs,
        )
        if not save_folder_path:
            raise ValueError("Save folder path must be provided.")
        if not file_type:
            raise ValueError("File type must be provided.")

        self.file_type = file_type
        self.save_folder_path = Path(save_folder_path)

    def _on_click(self):
        file_path = self.save_folder_path / self.file_name
        if self.file_name == "":
            raise ValueError("File name must be defined in the subclass.")

        if file_path.is_dir():
            MessageOverlay(
                f"There is already a saved file with the same name as the current {self.file_type}. Do you want to overwrite it?",
                button_commands={
                    "Yes": self._save,
                    "No (cancel)": lambda: None,
                },
                subject="Warning",
            )
        else:
            self._save()

    def _save(self):
        """
        Performs the save operation and shows a success message. Subclasses can
        override this to add the actual file-saving logic before calling super().
        """
        MessageOverlay(
            f"Sucessfully saved the {self.file_type}.",
            button_commands={
                "Ok": lambda: None,
            },
            subject="Success",
        )

    @property
    def file_name(self) -> str:
        """
        Returns the name of the file to save.
        NOTE: This property must be overridden in subclasses.
        """
        return ""
