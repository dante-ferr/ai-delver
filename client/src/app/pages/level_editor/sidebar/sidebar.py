import customtkinter as ctk
from .tools_frame.tools_frame import ToolsFrame
from .layers_panel.layers_panel import LayersPanel
from .canvas_objects_panel import CanvasObjectPanelsWrapper
from ._level_title_textbox import LevelTitleTextbox
from loaders import level_loader
from app.utils import verify_level_issues
from src.app.components import SectionTitle
from .bottom_frame import BottomFrame
from app.components import StandardButton
from src.config import config

class Sidebar(ctk.CTkFrame):

    def __init__(self, master):
        from ..level_editor_manager import level_editor_manager

        level_editor_manager.objects_manager.assign_level_to_objects(level_loader.level)

        super().__init__(master, fg_color="transparent")

        self.pack_propagate(False)

        level_editor_manager.selector.set_selection("layer", "platforms")

        title_textbox = LevelTitleTextbox(self)
        title_textbox.pack(padx=0, pady=0, fill="x")

        test_level_button = StandardButton(
            self, text="Test Level", command=self._test_level
        )
        test_level_button.pack(pady=(0, config.STYLE.SECTION_SPACING))

        layersPanel = LayersPanel(self)
        layersPanel.pack(pady=(0, config.STYLE.SECTION_SPACING), anchor="w", fill="x")

        edit_label = SectionTitle(self, text="Edit")
        edit_label.pack(pady=4, side="top", anchor="w")

        tools_frame_container = ctk.CTkFrame(self, fg_color="transparent")
        tools_frame_container.pack(pady=(0, config.STYLE.SECTION_SPACING), fill="x")
        tools_frame = ToolsFrame(tools_frame_container)
        tools_frame.pack(anchor="center")

        bottom_frame = BottomFrame(self)
        bottom_frame.pack(side="bottom", fill="x")

        canvas_objects_panels_wrapper = CanvasObjectPanelsWrapper(self)
        canvas_objects_panels_wrapper.pack(
            pady=0, padx=0, anchor="w", fill="both", expand=True
        )

    def _test_level(self):
        from app_manager import app_manager

        if not verify_level_issues():
            app_manager.start_game()
