import customtkinter as ctk
from src.config import config

class SectionTitle(ctk.CTkLabel):

    def __init__(self, master, text: str):
        super().__init__(
            master,
            text=text,
            font=ctk.CTkFont(size=config.STYLE.FONT.SUBTITLE_SIZE, weight="bold"),
            anchor="w",
            fg_color="transparent",
        )
