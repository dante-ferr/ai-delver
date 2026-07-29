import customtkinter as ctk
from app.fonts import app_font
from app.theme import theme, list_available_themes
from ..overlay import Overlay


class SettingsOverlay(Overlay):
    def __init__(self):
        super().__init__("General Settings")

        self.grid_columnconfigure(0, weight=1)

        # Header
        self.title_label = ctk.CTkLabel(
            self,
            text="Settings",
            font=app_font(size=16, weight="bold"),
            anchor="w",
        )
        self.title_label.pack(padx=16, pady=(16, 12), fill="x")

        # Container for setting rows
        self.settings_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.settings_frame.pack(padx=16, pady=(0, 16), fill="x")
        self.settings_frame.grid_columnconfigure(0, weight=1)
        self.settings_frame.grid_columnconfigure(1, weight=1)

        # Setting: Theme
        self.theme_label = ctk.CTkLabel(
            self.settings_frame,
            text="Theme:",
            font=app_font(size=13, weight="bold"),
            anchor="w",
        )
        self.theme_label.grid(row=0, column=0, sticky="w", pady=6)

        available_themes = list_available_themes()
        current_theme = theme.name if theme.name in available_themes else available_themes[0]

        self.theme_menu = ctk.CTkOptionMenu(
            self.settings_frame,
            values=available_themes,
            command=self._on_theme_selected,
            font=app_font(size=12),
        )
        self.theme_menu.set(current_theme)
        self.theme_menu.grid(row=0, column=1, sticky="e", pady=6)

        # Footer Actions
        self.footer = ctk.CTkFrame(self, fg_color="transparent")
        self.footer.pack(padx=16, pady=(0, 16), fill="x")

        self.close_btn = ctk.CTkButton(
            self.footer,
            text="Close",
            width=80,
            command=self._close,
        )
        self.close_btn.pack(side="right")

        self._post_init_config()

    def _on_theme_selected(self, selected_theme: str):
        from app_manager import app_manager

        theme.load(selected_theme)
        if app_manager.editor_app:
            app_manager.editor_app.reload_ui()

    def _post_init_config(self):
        self.minsize(width=340, height=200)
        self.maxsize(width=340, height=300)
        self.resizable(False, False)
        self._reveal()
