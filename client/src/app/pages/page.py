import customtkinter as ctk


class Page(ctk.CTkFrame):
    def __init__(self, master, display_name: str):
        super().__init__(master)

        self.display_name = display_name
