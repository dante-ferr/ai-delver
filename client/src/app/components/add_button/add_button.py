from app.components import IconButton
from src.config import config


class AddButton(IconButton):

    def __init__(self, master, **kwargs):
        super().__init__(
            master, svg_path=str(config.ASSETS_PATH / "svg" / "plus.svg"), **kwargs
        )
