import customtkinter as ctk
from .sidebar import Sidebar
from .level_canvas import LevelCanvas
from .. import Page


class LevelEditor(Page):

    def __init__(self, master):
        super().__init__(master, "Level Editor")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=256)

        left_frame = ctk.CTkFrame(self, fg_color="transparent")
        left_frame.grid(row=0, column=0, sticky="nsew")
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(0, weight=0)
        left_frame.grid_rowconfigure(1, weight=1)

        canvas = LevelCanvas(left_frame)
        canvas.grid(row=1, column=0, sticky="nsew")

        sidebar = Sidebar(self)
        sidebar.grid(row=0, column=1, sticky="ns", padx=16, pady=32)
