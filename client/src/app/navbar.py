import customtkinter as ctk
from loaders import level_loader, agent_loader
from state_managers import training_state_manager
from src.config import config
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pages.page import Page


class Navbar(ctk.CTkFrame):
    """Session chrome: brand, page modes, contextual document, system status."""

    def __init__(self, master):
        nav = config.STYLE.NAVBAR
        super().__init__(
            master,
            fg_color=("gray86", "gray17"),
            height=nav.HEIGHT,
            corner_radius=0,
        )
        self.master = master
        self._page_by_display: dict[str, str] = {}
        self._display_by_page: dict[str, str] = {}
        self._suppress_tab_command = False

        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)
        self.grid_rowconfigure(0, weight=1)

        pad_x = nav.PAD_X
        pad_y = nav.PAD_Y

        self._left = ctk.CTkFrame(self, fg_color="transparent")
        self._left.grid(row=0, column=0, sticky="w", padx=(pad_x, 0), pady=pad_y)

        self._brand = ctk.CTkLabel(
            self._left,
            text=nav.BRAND,
            font=ctk.CTkFont(
                size=config.STYLE.FONT.STANDARD_SIZE,
                weight="bold",
            ),
        )
        self._brand.pack(side="left", padx=(0, nav.BRAND_GAP))

        self._tab_button: ctk.CTkSegmentedButton | None = None

        self._title_label = ctk.CTkLabel(
            self,
            text="",
            anchor="center",
            font=ctk.CTkFont(size=config.STYLE.FONT.SMALL_SIZE),
            text_color=("gray40", nav.STATUS_MUTED_COLOR),
        )
        self._title_label.grid(row=0, column=1, sticky="ew", padx=8, pady=pad_y)

        self._right = ctk.CTkFrame(self, fg_color="transparent")
        self._right.grid(row=0, column=2, sticky="e", padx=(0, pad_x), pady=pad_y)

        self._training_label = ctk.CTkLabel(
            self._right,
            text="",
            font=ctk.CTkFont(size=config.STYLE.FONT.SMALL_SIZE),
            text_color=nav.STATUS_TRAINING_COLOR,
        )
        self._training_label.pack(side="right", padx=(12, 0))

        self._status_label = ctk.CTkLabel(
            self._right,
            text="",
            font=ctk.CTkFont(size=config.STYLE.FONT.SMALL_SIZE),
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
        nav = config.STYLE.NAVBAR
        pad = " " * int(nav.TAB_PAD_CHARS)

        def _tab_label(display_name: str) -> str:
            return f"{pad}{display_name}{pad}"

        self._page_by_display = {
            _tab_label(page.display_name): page_name
            for page_name, page in pages.items()
        }
        self._display_by_page = {
            page_name: _tab_label(page.display_name)
            for page_name, page in pages.items()
        }

        if default_page_name not in self._display_by_page:
            raise ValueError("The default page doesn't exist")

        display_names = [_tab_label(page.display_name) for page in pages.values()]
        self._tab_button = ctk.CTkSegmentedButton(
            self._left,
            values=display_names,
            command=self._on_tab_selected,
            font=ctk.CTkFont(size=nav.TAB_FONT_SIZE),
            height=nav.TAB_HEIGHT,
        )
        self._tab_button.pack(side="left")
        self._tab_button.set(self._display_by_page[default_page_name])
        self.master.select_page(default_page_name)

    def select_page(self, page_name: str) -> None:
        """Select a page via the navbar so the highlight stays in sync."""
        if getattr(self.master, "selected_page_name", None) == page_name:
            return

        display_name = self._display_by_page.get(page_name)
        if display_name is None:
            raise ValueError(f"Unknown page '{page_name}'")

        if self._tab_button is not None and self._tab_button.get() != display_name:
            self._suppress_tab_command = True
            try:
                self._tab_button.set(display_name)
            finally:
                self._suppress_tab_command = False

        self.master.select_page(page_name)

    def _on_tab_selected(self, display_name: str) -> None:
        if self._suppress_tab_command:
            return
        page_name = self._page_by_display.get(display_name)
        if page_name is None:
            return
        if getattr(self.master, "selected_page_name", None) == page_name:
            return
        self.master.select_page(page_name)

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
