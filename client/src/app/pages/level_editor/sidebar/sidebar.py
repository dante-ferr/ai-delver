import customtkinter as ctk
from .tools_frame.tools_frame import ToolsFrame
from .layers_panel.layers_panel import LayersPanel
from .canvas_objects_panel import CanvasObjectPanelsWrapper
from ._level_title_textbox import LevelTitleTextbox
from loaders import level_loader
from app.utils import verify_level_issues
from src.app.components import SectionTitle
from .bottom_frame import BottomFrame
from app.components import StandardButton, MouseWheelScrollableFrame
from src.config import config


class Sidebar(ctk.CTkFrame):

    def __init__(self, master):
        from ..level_editor_manager import level_editor_manager

        level_editor_manager.objects_manager.assign_level_to_objects(level_loader.level)

        super().__init__(master, fg_color="transparent")

        level_editor_manager.selector.set_selection("layer", "platforms")

        # ------------------------------------------------------------- Side Frame
        self.side_frame = ctk.CTkFrame(self, fg_color="transparent")

        self.side_title_textbox = LevelTitleTextbox(self.side_frame)
        self.side_test_level_button = StandardButton(
            self.side_frame,
            text="Test Level",
            command=self._test_level,
            svg_path=str(config.ASSETS_PATH / "svg" / "test.svg"),
        )
        self.side_layers_panel = LayersPanel(self.side_frame)
        self.side_edit_label = SectionTitle(self.side_frame, text="Edit")
        self.side_tools_frame_container = ctk.CTkFrame(self.side_frame, fg_color="transparent")
        self.side_tools_frame = ToolsFrame(self.side_tools_frame_container)
        self.side_tools_frame.pack(anchor="center")
        self.side_canvas_objects_wrapper = CanvasObjectPanelsWrapper(self.side_frame)
        self.side_bottom_frame = BottomFrame(self.side_frame)

        self.side_title_textbox.pack(padx=0, pady=0, fill="x")
        self.side_test_level_button.pack(pady=(0, config.STYLE.SECTION_SPACING))
        self.side_layers_panel.pack(pady=(0, config.STYLE.SECTION_SPACING), anchor="w", fill="x")
        self.side_edit_label.pack(pady=4, side="top", anchor="w")
        self.side_tools_frame_container.pack(pady=(0, config.STYLE.SECTION_SPACING), fill="x")
        self.side_bottom_frame.pack(side="bottom", fill="x")
        self.side_canvas_objects_wrapper.pack(pady=0, padx=0, anchor="w", fill="both", expand=True)
        self.side_canvas_objects_wrapper.set_mode("side")

        # ----------------------------------------------------------- Bottom Frame
        # Horizontal MouseWheelScrollableFrame ensures ALL elements fit on narrow windows
        self.bottom_scroll_frame = MouseWheelScrollableFrame(
            self, fg_color="transparent", height=170, orientation="horizontal"
        )
        self.bottom_scroll_frame.configure(border_width=0)

        # Section 1: Info (Title & Test Level)
        self.b_info_frame = ctk.CTkFrame(self.bottom_scroll_frame, fg_color="transparent")
        self.b_title_textbox = LevelTitleTextbox(self.b_info_frame)
        self.b_test_level_button = StandardButton(
            self.b_info_frame,
            text="Test Level",
            command=self._test_level,
            svg_path=str(config.ASSETS_PATH / "svg" / "test.svg"),
        )
        self.b_title_textbox.pack(padx=0, pady=(0, 6), fill="x")
        self.b_test_level_button.pack(pady=0)
        self.b_info_frame.pack(side="left", padx=(0, 12), pady=2, anchor="n")

        # Section 2: Edit Tools
        self.b_tools_frame_section = ctk.CTkFrame(self.bottom_scroll_frame, fg_color="transparent")
        self.b_edit_label = SectionTitle(self.b_tools_frame_section, text="Edit")
        self.b_tools_container = ctk.CTkFrame(self.b_tools_frame_section, fg_color="transparent")
        self.b_tools_frame = ToolsFrame(self.b_tools_container)
        self.b_tools_frame.pack(anchor="center")

        self.b_edit_label.pack(pady=(0, 2), anchor="w")
        self.b_tools_container.pack(pady=0, fill="x")
        self.b_tools_frame_section.pack(side="left", padx=12, pady=2, anchor="n")

        # Section 3: Layers Panel (Side-by-side section, not stacked under tools!)
        self.b_layers_frame_section = ctk.CTkFrame(self.bottom_scroll_frame, fg_color="transparent")
        self.b_layers_panel = LayersPanel(self.b_layers_frame_section)
        self.b_layers_panel.pack(pady=0, fill="x")
        self.b_layers_frame_section.pack(side="left", padx=12, pady=2, anchor="n")

        # Section 4: Objects Panel
        self.b_objects_frame = ctk.CTkFrame(self.bottom_scroll_frame, fg_color="transparent")
        self.b_canvas_objects_wrapper = CanvasObjectPanelsWrapper(self.b_objects_frame)
        self.b_canvas_objects_wrapper.pack(pady=0, padx=0, fill="both", expand=True)
        self.b_canvas_objects_wrapper.set_mode("bottom")
        self.b_objects_frame.pack(side="left", padx=12, pady=2, anchor="n")

        # Section 5: Controls (Zoom, Grid, Resize Level, File Loader)
        self.b_controls_frame = ctk.CTkFrame(self.bottom_scroll_frame, fg_color="transparent")
        self.b_bottom_frame = BottomFrame(self.b_controls_frame)
        self.b_bottom_frame.pack(fill="both", expand=True)
        self.b_controls_frame.pack(side="left", padx=(12, 0), pady=2, anchor="n")

        self._mode: str | None = None
        self.set_mode("side")

    def set_mode(self, mode: str):
        if self._mode == mode:
            return
        self._mode = mode

        if mode == "side":
            self.bottom_scroll_frame.pack_forget()
            self.configure(width=256)
            self.pack_propagate(False)
            self.side_layers_panel.set_mode("side")
            self.side_canvas_objects_wrapper.set_mode("side")
            self.side_frame.pack(fill="both", expand=True)
        else:
            self.side_frame.pack_forget()
            self.configure(width=0)
            self.pack_propagate(True)
            self.b_layers_panel.set_mode("bottom")
            self.b_canvas_objects_wrapper.set_mode("bottom")
            self.bottom_scroll_frame.pack(fill="x", expand=True, padx=0, pady=0)
            self.bottom_scroll_frame.bind_scroll_events_recursively(self.bottom_scroll_frame)
            self.bottom_scroll_frame.after(50, self.bottom_scroll_frame._check_scroll_visibility)

    def _test_level(self):
        from app_manager import app_manager

        if not verify_level_issues():
            app_manager.start_game()
