import customtkinter as ctk
from ._agent_save_button import AgentSaveButton
from ._agent_load_button import AgentLoadButton


class AgentFileContainer(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        save_button = AgentSaveButton(self)
        save_button.pack(side="left", padx=0, pady=0)

        load_button = AgentLoadButton(self)
        load_button.pack(padx=0, pady=0)
