import customtkinter as ctk
from ._level_list import LevelList
from ._level_add_button import LevelAddButton
from app.components import SectionTitle
from typing import Callable
from src.config import config


class LevelSelector(ctk.CTkFrame):

    def __init__(self, master, on_amount_of_episodes_change: Callable, *args):
        super().__init__(master, *args, height=240, fg_color="transparent")

        section_title = SectionTitle(self, "Training Levels")
        section_title.pack(anchor="w", pady=(0, 8))

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 2))

        first_label = ctk.CTkLabel(
            header,
            text="First to train...",
            font=ctk.CTkFont(size=config.STYLE.FONT.SMALL_SIZE),
        )
        first_label.pack(side="left", pady=0)

        level_add_button = LevelAddButton(header)
        level_add_button.pack(side="right", pady=0)

        self.level_list = LevelList(self, on_amount_of_episodes_change)
        self.level_list.pack(fill="both")

        last_label = ctk.CTkLabel(
            self,
            text="... last to train",
            font=ctk.CTkFont(size=config.STYLE.FONT.SMALL_SIZE),
        )
        last_label.pack(anchor="e", pady=(2, 0))
