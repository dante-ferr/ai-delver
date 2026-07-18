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
            world_object_args: Args forwarded when creating the underlying world object.
        """
        self.name = name
        self.world_object_args = world_object_args or {}

        self._create_element_callback: Callable | None = None
        self._remove_element_callback: Callable | None = None

        self.image = Image.open(image_path)
        self.layer: "CanvasObjectsLayer | None" = None

    @property
    def size(self) -> tuple[int, int]:
        """Footprint in tiles (width, height). Defaults to 1x1."""
        raw = self.world_object_args.get("size", (1, 1))
        return (int(raw[0]), int(raw[1]))

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
        return self._remove_element_callback

    @remove_element_callback.setter
    def remove_element_callback(self, callback: Callable):
        self._remove_element_callback = callback
