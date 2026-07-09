import customtkinter as ctk
from src.config import config
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...level_editor_manager.canvas_objects import CanvasObject


class CanvasObjectContainer(ctk.CTkFrame):
    image_size = (32, 32)

    def __init__(self, master, canvas_object: "CanvasObject"):
        super().__init__(master, fg_color="transparent")
        self.canvas_object = canvas_object

        image = ctk.CTkImage(canvas_object.image, size=self.image_size)
        label = ctk.CTkLabel(
            self,
            image=image,
            text="",
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        label.pack(padx=3.2, pady=3.2)
