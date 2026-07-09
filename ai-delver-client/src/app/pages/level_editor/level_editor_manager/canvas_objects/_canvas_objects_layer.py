from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .canvas_object import CanvasObject


class CanvasObjectsLayer:
    def __init__(self, name: str):
        self.name = name

        self.canvas_objects: dict[str, "CanvasObject"] = {}

    def add_canvas_object(self, canvas_object: "CanvasObject"):
        self.canvas_objects[canvas_object.name] = canvas_object
        canvas_object.layer = self

    def get_canvas_object(self, canvas_object_name: str) -> "CanvasObject":
        return self.canvas_objects[canvas_object_name]
