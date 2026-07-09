from app.components import IconButton
from src.config import config
from typing import Callable


class DeleteButton(IconButton):
    def __init__(self, master, command: Callable):
        super().__init__(
            master,
            svg_path=str(config.ASSETS_PATH / "svg" / "x.svg"),
            command=command,
            width=15,
            height=15,
            fg_color="transparent",
            hover_color=("gray70", "gray40"),
            text_color="white",
            corner_radius=6,
        )
