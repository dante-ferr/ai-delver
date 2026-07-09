import customtkinter as ctk
from src.config import config


class StandardButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("font", ("Arial", config.STYLE.FONT.STANDARD_SIZE, "bold"))
        kwargs.setdefault("height", 32)
        super().__init__(master, **kwargs)
