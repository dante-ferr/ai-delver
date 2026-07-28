import customtkinter as ctk
from app.fonts import app_font


class ActionSequencePopup(ctk.CTkToplevel):
    """Popup showing the compressed action-change timeline for the selected run."""

    def __init__(self, master, timeline_text: str):
        super().__init__(master)
        self.title("Action Sequence")
        self.geometry("420x520")
        self.minsize(320, 280)
        self.lift()
        self.focus_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkLabel(
            self,
            text="Action Sequence",
            font=app_font(size=16, weight="bold"),
            anchor="w",
        )
        header.grid(row=0, column=0, padx=16, pady=(14, 6), sticky="ew")

        self.textbox = ctk.CTkTextbox(self, wrap="none")
        self.textbox.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self.set_timeline(timeline_text)

    def set_timeline(self, text: str):
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.insert(
            "1.0",
            text
            or "Trajectory actions will be listed here chronologically once loaded.",
        )
        self.textbox.configure(state="disabled")
