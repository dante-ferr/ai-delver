import customtkinter as ctk
from app.fonts import app_font
from PIL import Image
from loaders import level_loader, agent_loader
from state_managers import training_state_manager
from src.config import config
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pages.page import Page


from app.theme import theme


class Navbar(ctk.CTkFrame):
    """Session chrome: brand, page modes, contextual document, system status."""

    def __init__(self, master):
        nav = config.STYLE.NAVBAR
        super().__init__(
            master,
            fg_color=("gray86", theme.bg_dark_mid),
            height=nav.HEIGHT,
            corner_radius=0,
        )
        self.master = master
        self._page_by_display: dict[str, str] = {}
        self._display_by_page: dict[str, str] = {}
        self._suppress_tab_command = False

        self.grid_propagate(False)

        # 3-column layout: Left (Brand + Page tabs), Center (Title), Right (Controls/Status)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)

        pad_x = nav.PAD_X
        pad_y = nav.PAD_Y

        self._left = ctk.CTkFrame(self, fg_color="transparent")
        self._left.grid(row=0, column=0, sticky="w", padx=(pad_x, 0), pady=pad_y)

        favicon_size = int(nav.FAVICON_SIZE)
        favicon_image = Image.open(config.ASSETS_PATH / "img" / "favicon.png")
        self._favicon = ctk.CTkImage(
            light_image=favicon_image,
            dark_image=favicon_image,
            size=(favicon_size, favicon_size),
        )
        self._favicon_label = ctk.CTkLabel(
            self._left,
            text="",
            image=self._favicon,
        )
        self._favicon_label.pack(side="left", padx=(0, nav.FAVICON_GAP))

        self._brand = ctk.CTkLabel(
            self._left,
            text=nav.BRAND,
            text_color=theme.primary_color,
            font=app_font(
                size=config.STYLE.FONT.STANDARD_SIZE,
                weight="bold",
            ),
        )
        self._brand.pack(side="left", padx=(0, nav.BRAND_GAP))

        self._title_label = ctk.CTkLabel(
            self,
            text="",
            anchor="center",
            font=app_font(size=config.STYLE.FONT.SMALL_SIZE),
            text_color=("gray40", theme.text_light),
        )
        self._title_label.grid(row=0, column=1, sticky="ew", padx=8, pady=pad_y)

        self._right = ctk.CTkFrame(self, fg_color="transparent")
        self._right.grid(row=0, column=2, sticky="e", padx=(0, pad_x), pady=pad_y)

        self._training_label = ctk.CTkLabel(
            self._right,
            text="",
            font=app_font(size=config.STYLE.FONT.SMALL_SIZE),
            text_color=nav.STATUS_TRAINING_COLOR,
        )
        self._training_label.pack(side="right", padx=(12, 0))

        self._status_label = ctk.CTkLabel(
            self._right,
            text="",
            font=app_font(size=config.STYLE.FONT.SMALL_SIZE),
        )
        self._status_label.pack(side="right")

        level_loader.add_dirty_listener(lambda _dirty: self.refresh_document_title())
        agent_loader.add_dirty_listener(lambda _dirty: self.refresh_document_title())
        training_state_manager.add_callback(
            "connected_to_server", lambda _value: self.refresh_status()
        )
        training_state_manager.add_callback(
            "training", lambda _value: self.refresh_status()
        )
        self.refresh_status()

    def create_page_selectors(self, pages: dict[str, "Page"], default_page_name: str):
        from app.components import StandardButton

        self._page_buttons: dict[str, StandardButton] = {}
        self._page_icon_paths = {
            "level_editor": str(config.ASSETS_PATH / "svg" / "pencil.svg"),
            "agent": str(config.ASSETS_PATH / "svg" / "agent.svg"),
        }

        self._tabs_container = ctk.CTkFrame(self._left, fg_color="transparent")
        self._tabs_container.pack(side="left", padx=(4, 0))

        for page_name, page in pages.items():
            icon_path = self._page_icon_paths.get(page_name)
            btn = StandardButton(
                self._tabs_container,
                text=page.display_name,
                svg_path=icon_path,
                command=lambda p=page_name: self._on_page_btn_clicked(p),
                height=28,
            )
            btn.pack(side="left", padx=2)
            self._page_buttons[page_name] = btn

        from app.components import IconButton
        gear_icon_path = str(config.ASSETS_PATH / "svg" / "gear.svg")
        self.settings_btn = IconButton(
            self._tabs_container,
            svg_path=gear_icon_path,
            command=self._open_settings_popup,
            width=20,
            height=20,
        )
        self.settings_btn.pack(side="left", padx=(8, 2))

        self.select_page(default_page_name)

    def select_page(self, page_name: str) -> None:
        """Select a page via the navbar so the highlight stays in sync."""
        if getattr(self.master, "selected_page_name", None) == page_name:
            return

        for name, btn in getattr(self, "_page_buttons", {}).items():
            if name == page_name:
                btn.configure(fg_color=theme.secondary_dark, text_color=theme.primary_color)
            else:
                btn.configure(fg_color="transparent", text_color=theme.text_slate)

        self.master.select_page(page_name)

    def _on_page_btn_clicked(self, page_name: str) -> None:
        self.select_page(page_name)

    def _open_settings_popup(self) -> None:
        from app.components.overlay import SettingsOverlay
        SettingsOverlay()

    def refresh_document_title(self) -> None:
        page_name = getattr(self.master, "selected_page_name", None)
        nav = config.STYLE.NAVBAR
        max_chars = int(nav.TITLE_MAX_CHARS)

        if page_name == "level_editor":
            kind = "Level"
            name = level_loader.level.name
            dirty = level_loader.dirty
        elif page_name == "agent":
            kind = "Agent"
            name = agent_loader.agent.name
            dirty = agent_loader.dirty
        else:
            self._title_label.configure(text="")
            return

        display_name = name.strip() or "Untitled"
        if len(display_name) > max_chars:
            display_name = display_name[: max(1, max_chars - 1)] + "…"

        dirty_prefix = "* " if dirty else ""
        self._title_label.configure(text=f"{kind}  ·  {dirty_prefix}{display_name}")

    def refresh_status(self) -> None:
        nav = config.STYLE.NAVBAR
        connected = training_state_manager.get_value("connected_to_server")
        if connected == "yes":
            status_text = "●  Server"
            status_color = nav.STATUS_CONNECTED_COLOR
        elif connected == "loading":
            status_text = "●  Connecting…"
            status_color = nav.STATUS_LOADING_COLOR
        else:
            status_text = "●  Offline"
            status_color = nav.STATUS_DISCONNECTED_COLOR

        self._status_label.configure(text=status_text, text_color=status_color)

        if training_state_manager.get_value("training"):
            activity = (
                "Playing…"
                if training_state_manager.play_session
                else "Training…"
            )
            self._training_label.configure(text=activity)
        else:
            self._training_label.configure(text="")
