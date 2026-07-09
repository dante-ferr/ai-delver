import customtkinter as ctk
from src.config import config


class TrainProcessLog(ctk.CTkFrame):
    """A base CustomTkinter container for displaying training progress."""

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        main_process_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_process_frame.pack()

        main_process_frame.grid_columnconfigure(0, weight=1)

        self.label = ctk.CTkLabel(
            main_process_frame,
            text="",
            anchor="w",
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        )
        self.label.grid(row=0, column=0, padx=0, pady=2, sticky="ew")

        self.progress_bar = ctk.CTkProgressBar(main_process_frame, mode="determinate")
        self.progress_bar.grid(row=1, column=0, padx=0, pady=(0, 5), sticky="ew")
        self.progress_bar.set(0)

    def update_progress(self, current_step: int):
        raise NotImplementedError("Subclasses must implement update_progress")
