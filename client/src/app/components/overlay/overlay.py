import customtkinter as ctk


class Overlay(ctk.CTkToplevel):
    def __init__(self, title: str):
        from app_manager import app_manager

        super().__init__(app_manager.editor_app)

        self.attributes("-topmost", True)
        self.attributes("-type", "dialog")

        self.title(title)

        self.after(10, self.grab_set)
        self._post_init_config()

    def _close(self):
        self.grab_release()
        self.destroy()

    def center(self):
        self.update_idletasks()
        x = (
            self.master.winfo_x()
            + (self.master.winfo_width() // 2)
            - (self.winfo_reqwidth() // 2)
        )
        y = (
            self.master.winfo_y()
            + (self.master.winfo_height() // 2)
            - (self.winfo_reqheight() // 2)
        )
        self.geometry(f"+{x}+{y}")

    def _post_init_config(self):
        self.minsize(width=320, height=160)
        self.maxsize(width=320, height=480)
        self.resizable(False, False)
        self.center()
