from ._selector import LevelSelector
from .canvas_objects import CanvasObjectsManager


class LevelEditorManager:
    def __init__(self):
        self.selector = LevelSelector()
        self.objects_manager = CanvasObjectsManager()


level_editor_manager = LevelEditorManager()
