import customtkinter as ctk
from src.config import config

class LoadingLog(ctk.CTkFrame):
    """A CustomTkinter container for displaying a single loading log entry."""

    def __init__(self, master, text: str):
        super().__init__(master, fg_color="transparent")

        self.grid_columnconfigure(1, weight=1)

        self.progress_bar = ctk.CTkProgressBar(self, mode="indeterminate", width=50)
        self.progress_bar.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")
        self.progress_bar.start()

        self.label = ctk.CTkLabel(
            self,
            text=text,
            anchor="w",
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE, weight="bold"),
        )
        self.label.grid(row=0, column=1, padx=0, pady=5, sticky="ew")
