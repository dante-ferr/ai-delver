import shutil
from pathlib import Path

from app.components.overlay.file_loader_overlay import FileLoaderOverlay
from app.components.overlay.message_overlay import MessageOverlay


class FileDeleterOverlay(FileLoaderOverlay):
    """Modal picker for choosing a saved file directory to permanently delete."""

    def __init__(
        self,
        file_dirs: dict[str, Path],
        file_type: str,
        show_sucess_message: bool = True,
    ):
        super().__init__(file_dirs, file_type, show_sucess_message=False)
        self._show_delete_success = show_sucess_message

    def _prompt_text(self) -> str:
        return f"Choose a {self.file_type} file to delete."

    def _action_button_text(self) -> str:
        return "Delete"

    def _on_action(self):
        if not self._rows:
            return
        query = self._filter_var.get().strip().lower()
        if query and query not in self._selected_name.lower():
            return

        selected_name = self._selected_name
        self._close()
        MessageOverlay(
            f"Are you sure you want to permanently delete the {self.file_type} "
            f'"{selected_name}"? This cannot be undone.',
            subject="Warning",
            button_commands={
                "Yes": lambda: self._delete(selected_name),
                "No (cancel)": lambda: None,
            },
        )

    def _delete(self, selected_name: str):
        file_path = self.file_dirs[selected_name]
        try:
            shutil.rmtree(file_path)
        except Exception as e:
            MessageOverlay(
                f"Failed to delete the {self.file_type}: {e}",
                subject="Error",
            )
            return

        if self._show_delete_success:
            MessageOverlay(
                f'Sucessfully deleted the {self.file_type} "{selected_name}".',
                subject="Success",
            )
