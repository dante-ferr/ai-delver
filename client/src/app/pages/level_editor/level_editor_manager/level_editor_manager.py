from ._selector import LevelSelector
from .canvas_objects import CanvasObjectsManager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..sidebar.tools_frame.tools_frame import ToolsFrame


class LevelEditorManager:
    def __init__(self):
        self.selector = LevelSelector()
        self.objects_manager = CanvasObjectsManager()
        self.tools_frame: "ToolsFrame | None" = None


level_editor_manager = LevelEditorManager()
