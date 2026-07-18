import customtkinter as ctk
from app.components import SvgImage
from app.theme import theme
from app.utils.selection import populate_selection_manager, SelectionManager
from ...level_editor_manager import level_editor_manager
from src.config import config


class ToolBox(ctk.CTkFrame):

    def __init__(self, master, tool_name: str, icon_image: ctk.CTkImage):
        super().__init__(master)
        self.tool_name = tool_name

        label = ctk.CTkLabel(
            self,
            image=icon_image,
            text="",
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        label.pack(padx=4.8, pady=4.8)


class ToolsFrame(ctk.CTkFrame):

    def __init__(self, master):
        from state_managers import canvas_state_manager

        super().__init__(master, fg_color="transparent")

        self.tool_boxes = self._create_tool_boxes()
        self._grid_tool_boxes()
        self._create_brush_size_slider(canvas_state_manager)

        def _on_select(frame: "ToolBox"):
            level_editor_manager.selector.set_selection("tool", frame.tool_name)

        self.selection_manager = SelectionManager()
        populate_selection_manager(
            self.selection_manager,
            frames=self.tool_boxes,
            default_frame=self.tool_boxes[0],
            on_select=_on_select,
        )

        level_editor_manager.tools_frame = self

    def select_tool(self, tool_name: str):
        for group in self.selection_manager.selection_element_groups:
            frame = group.frame
            if isinstance(frame, ToolBox) and frame.tool_name == tool_name:
                self.selection_manager.selected_element_group = group
                return

    def _grid_tool_boxes(self):
        for i, tool_box in enumerate(self.tool_boxes):
            tool_box.grid(row=0, column=i, padx=1)

    def _create_brush_size_slider(self, canvas_state_manager):
        size_container = ctk.CTkFrame(self, fg_color="transparent")
        size_container.grid(
            row=1, column=0, columnspan=max(len(self.tool_boxes), 1), pady=(8, 0)
        )

        size_label = ctk.CTkLabel(
            size_container,
            text="Size",
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        size_label.pack(padx=(0, 4), anchor="w")

        number_of_steps = config.MAX_BRUSH_SIZE - config.MIN_BRUSH_SIZE
        size_slider = ctk.CTkSlider(
            size_container,
            from_=config.MIN_BRUSH_SIZE,
            to=config.MAX_BRUSH_SIZE,
            number_of_steps=number_of_steps,
            width=128,
            command=lambda value: canvas_state_manager.set_value(
                "brush_size", int(round(float(value)))
            ),
        )
        size_slider.set(int(canvas_state_manager.get_value("brush_size")))
        size_slider.pack()

        def _sync_slider(value):
            size_slider.set(int(round(float(value))))

        canvas_state_manager.add_callback("brush_size", _sync_slider)

    def _create_tool_boxes(self):
        tool_size = 24

        pen_icon = SvgImage(
            svg_path=str(config.ASSETS_PATH / "svg" / "pencil.svg"),
            size=(tool_size, tool_size),
            stroke=theme.icon_color,
        )
        pen_box = ToolBox(self, "pencil", pen_icon.get_ctk_image())

        eraser_icon = SvgImage(
            svg_path=str(config.ASSETS_PATH / "svg" / "eraser.svg"),
            fill=theme.icon_color,
            stroke=theme.icon_color,
            size=(tool_size, tool_size),
        )
        eraser_box = ToolBox(self, "eraser", eraser_icon.get_ctk_image())

        return [pen_box, eraser_box]
