import customtkinter as ctk


class Overlay(ctk.CTkToplevel):
    def __init__(self, title: str):
        from app_manager import app_manager

        parent = app_manager.editor_app
        super().__init__(parent)

        # Withdraw before dialog/transient hints are applied. Otherwise tiling WMs
        # (notably Hyprland) map the Toplevel as a normal tiled client and never
        # re-classify it when -type dialog is set afterwards.
        self.withdraw()
        self.transient(parent)
        self.attributes("-type", "dialog")
        self.attributes("-topmost", True)

        self.title(title)

        self.after(10, self.grab_set)
        # Subclasses call _post_init_config() after building their UI so reveal
        # happens with the final size and hints already in place.

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

    def _reveal(self):
        """Center and map the window after size/hints are configured."""
        self.center()
        self.deiconify()
        self.lift()

    def _post_init_config(self):
        self.minsize(width=320, height=160)
        self.maxsize(width=320, height=480)
        self.resizable(False, False)
        self._reveal()
