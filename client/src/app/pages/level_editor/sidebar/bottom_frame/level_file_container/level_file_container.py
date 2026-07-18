import customtkinter as ctk
from ._level_save_button import LevelSaveButton
from ._level_load_button import LevelLoadButton
from ._level_delete_button import LevelDeleteButton


class LevelFileContainer(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        save_button = LevelSaveButton(self)
        save_button.pack(side="left", padx=0, pady=0)

        load_button = LevelLoadButton(self)
        load_button.pack(side="left", padx=0, pady=0)

        delete_button = LevelDeleteButton(self)
        delete_button.pack(side="left", padx=0, pady=0)
