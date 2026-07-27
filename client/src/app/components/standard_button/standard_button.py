import customtkinter as ctk
from app.fonts import app_font
from src.config import config


class StandardButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        kwargs.setdefault(
            "font",
            app_font(size=config.STYLE.FONT.STANDARD_SIZE, weight="bold"),
        )
        kwargs.setdefault("height", 32)
        super().__init__(master, **kwargs)
