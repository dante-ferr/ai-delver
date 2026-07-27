import customtkinter as ctk
from app.utils.selection import populate_selection_manager, SelectionManager
from src.config import config
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pages.page import Page
    from app.utils.selection import SelectionElementGroup


class SelectorFrame(ctk.CTkFrame):

    def __init__(self, master, page_name: str):
        super().__init__(master, fg_color="transparent")
        self.page_name = page_name


class Navbar(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master, fg_color="transparent", height=32)
        self.master = master
        self._selection_manager: SelectionManager | None = None
        self._page_groups: dict[str, "SelectionElementGroup"] = {}

    def create_page_selectors(self, pages: dict[str, "Page"], default_page_name: str):
        selector_frames: list[ctk.CTkFrame] = []

        default_frame = None

        for page_name, page in pages.items():
            selector_frame = SelectorFrame(self, page_name)
            selector_frame.pack(side="left")

            selector = ctk.CTkLabel(
                selector_frame,
                text=page.display_name,
                fg_color="transparent",
                font=ctk.CTkFont(size=config.STYLE.FONT.SMALL_SIZE),
            )
            selector.pack(padx=16)

            if page_name == default_page_name:
                default_frame = selector_frame

            selector_frames.append(selector_frame)

        if default_frame is None:
            raise ValueError("The default page doesn't exist")

        self._selection_manager = SelectionManager()
        populate_selection_manager(
            self._selection_manager,
            frames=selector_frames,
            default_frame=default_frame,
            on_select=lambda frame: self.master.select_page(frame.page_name),
        )
        self._page_groups = {
            group.frame.page_name: group
            for group in self._selection_manager.selection_element_groups
        }

    def select_page(self, page_name: str) -> None:
        """Select a page via the navbar so the highlight stays in sync."""
        if self._selection_manager is None:
            self.master.select_page(page_name)
            return
        group = self._page_groups.get(page_name)
        if group is None:
            raise ValueError(f"Unknown page '{page_name}'")
        if self._selection_manager.selected_element_group is group:
            return
        self._selection_manager.selected_element_group = group
