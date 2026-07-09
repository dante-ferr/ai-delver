from app.components.overlay.message_overlay import MessageOverlay
from app.components.overlay import Overlay
import customtkinter as ctk
from pathlib import Path
from src.config import config

class FileLoaderOverlay(Overlay):

    def __init__(
        self,
        file_dirs: dict[str, Path],
        file_type: str,
        show_sucess_message: bool = True,
    ):
        from app.components import StandardButton

        super().__init__("file_loader")

        self.file_dirs = file_dirs
        self.file_type = file_type
        self.show_sucess_message = show_sucess_message

        label = ctk.CTkLabel(
            self,
            text=f"Choose a {file_type} file to load.",
            height=100,
            wraplength=240,
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        label.pack(pady=0, anchor="w", fill="x")

        interaction_container = ctk.CTkFrame(self, fg_color="transparent")
        interaction_container.pack(pady=4)

        available_files = list(self.file_dirs.keys())

        self.option_menu = ctk.CTkOptionMenu(
            interaction_container, values=available_files
        )
        self.option_menu.grid(row=0, column=0, padx=4)

        load_button = StandardButton(
            interaction_container,
            text="Load",
            command=self._load,
            width=32,
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        load_button.grid(row=0, column=1, padx=4)

        self._post_init_config()

    def _get_file_path(self):
        """Returns the path of the selected file. Must be called in the _load method."""
        return self.file_dirs[self.option_menu.get()]

    def _load(self):
        self._close()
        if self.show_sucess_message:
            MessageOverlay(
                f"Sucessfully loaded the {self.file_type}.", subject="Success"
            )
