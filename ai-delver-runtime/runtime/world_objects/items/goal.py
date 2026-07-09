from .item import Item
from runtime.config import ASSETS_PATH

class Goal(Item):

    def __init__(self, runtime, variation: str, render):
        super().__init__(
            runtime,
            sprite_path=str(ASSETS_PATH / f"img/representations/goal/{variation}.png"),
            render=render,
        )
