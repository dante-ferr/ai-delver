import customtkinter as ctk
from src.config import config
from .resize_level_dialog.resize_level_dialog import ResizeLevelDialog
from .level_file_container import LevelFileContainer
from app.components import StandardButton
from src.config import config

class BottomFrame(ctk.CTkFrame):
    GRID_CELL_SPACEMENT = {
        "padx": 8,
        "pady": 8,
    }

    def __init__(self, master):
        from state_managers import canvas_state_manager

        super().__init__(master, fg_color="transparent")

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        zoom_container = ctk.CTkFrame(self, fg_color="transparent")
        zoom_container.grid(row=0, column=0, **self.GRID_CELL_SPACEMENT)

        zoom_label = ctk.CTkLabel(
            zoom_container,
            text="Zoom",
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        zoom_label.pack(padx=(0, 4), anchor="w")

        number_of_steps = config.MAX_CANVAS_ZOOM - config.MIN_CANVAS_ZOOM
        zoom_slider = ctk.CTkSlider(
            zoom_container,
            from_=config.MIN_CANVAS_ZOOM,
            to=config.MAX_CANVAS_ZOOM,
            variable=canvas_state_manager.vars["zoom"],
            number_of_steps=number_of_steps,
            width=128,
        )
        zoom_slider.pack()

        def _callback(value):
            zoom_slider.set(value)

        canvas_state_manager.add_callback("zoom", _callback)

        canvas_state_manager.set_value("grid_lines", True)
        grid_toggle = ctk.CTkCheckBox(
            self,
            text="Grid",
            variable=canvas_state_manager.vars["grid_lines"],
            checkbox_width=20,
            checkbox_height=20,
            font=ctk.CTkFont(size=config.STYLE.FONT.SMALL_SIZE),
        )
        grid_toggle.grid(row=0, column=1, **self.GRID_CELL_SPACEMENT)

        level_file_container = LevelFileContainer(self)
        level_file_container.grid(row=1, column=0, **self.GRID_CELL_SPACEMENT)

        resize_level_button = StandardButton(
            self,
            text="Resize Level",
            command=self._open_resize_level_dialog,
            font=ctk.CTkFont(size=config.STYLE.FONT.SMALL_SIZE),
        )
        resize_level_button.grid(row=1, column=1, **self.GRID_CELL_SPACEMENT)

    def _open_resize_level_dialog(self):
        ResizeLevelDialog(self)
