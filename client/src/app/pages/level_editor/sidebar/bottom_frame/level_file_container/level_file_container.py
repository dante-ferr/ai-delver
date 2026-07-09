import customtkinter as ctk
from ._level_save_button import LevelSaveButton
from ._level_load_button import LevelLoadButton


class LevelFileContainer(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        save_button = LevelSaveButton(self)
        save_button.pack(side="left", padx=0, pady=0)

        load_button = LevelLoadButton(self)
        load_button.pack(padx=0, pady=0)
