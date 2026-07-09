from PIL import Image
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ._canvas_objects_layer import CanvasObjectsLayer


class CanvasObject:
    def __init__(
        self,
        name: str,
        image_path: str,
        world_object_args: dict[str, Any] | None = None,
    ):
        """
        Args:
            name: The name of the canvas object.
            image_path: The path to the image of the canvas object.
            create_element_callback: The function to call when the canvas object is created.
            remove_element_callback: The function to call when the canvas object is removed.
            unique: Whether the canvas object is unique.
            world_object_name: The name of the world object that the canvas object represents. By default, the name of the canvas object is used (the first parameter).
        """
        self.name = name
        self.world_object_args = world_object_args or {}

        self._create_element_callback: Callable | None = None
        self._remove_element_callback: Callable | None = None

        self.image = Image.open(image_path)
        self.layer: "CanvasObjectsLayer | None" = None

    @property
    def create_element_callback(self):
        if self._create_element_callback is None:
            raise ValueError(
                f"create_element_callback is not set for {self.name} canvas object."
            )
        return self._create_element_callback

    @create_element_callback.setter
    def create_element_callback(self, callback: Callable):
        self._create_element_callback = callback

    @property
    def remove_element_callback(self):
        if self._remove_element_callback is None:
            raise ValueError(
                f"remove_element_callback is not set for {self.name} canvas object."
            )
        return self._remove_element_callback

    @remove_element_callback.setter
    def remove_element_callback(self, callback: Callable):
        self._remove_element_callback = callback
