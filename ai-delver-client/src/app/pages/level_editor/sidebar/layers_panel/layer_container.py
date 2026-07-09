import customtkinter as ctk
from src.config import config

Color = tuple[str, str] | str


class LayerContainer(ctk.CTkFrame):
    active_color: Color = ("gray75", "gray25")
    inactive_color: Color = "transparent"

    def __init__(self, master, layer_name: str, icon_image: ctk.CTkImage):
        super().__init__(master, fg_color="transparent")
        self.layer_name = layer_name

        self.selected = False

        icon = ctk.CTkLabel(
            self,
            image=icon_image,
            text="",
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        icon.grid(row=0, column=0, padx=6.4)

        name_label = ctk.CTkLabel(
            self,
            text=layer_name.capitalize(),
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        name_label.grid(row=0, column=1)
