from PIL import Image
from ..level_editor_manager import level_editor_manager

class WorldObjectsImage:
    def __init__(self):
        self.images: dict[str, Image.Image] = {}

    def get_image(self, canvas_object_name: str) -> Image.Image:
        if canvas_object_name not in self.images:
            canvas_object = level_editor_manager.objects_manager.get_canvas_object(
                canvas_object_name
            )
            if not canvas_object:
                raise KeyError(f"Canvas object '{canvas_object_name}' not found.")
            self.images[canvas_object_name] = canvas_object.image

        return self.images[canvas_object_name]
