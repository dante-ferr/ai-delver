import customtkinter as ctk
from app.fonts import app_font
from src.config import config

class SectionTitle(ctk.CTkLabel):

    def __init__(self, master, text: str):
        super().__init__(
            master,
            text=text,
            font=app_font(size=config.STYLE.FONT.SUBTITLE_SIZE, weight="bold"),
            anchor="w",
            fg_color="transparent",
        )
