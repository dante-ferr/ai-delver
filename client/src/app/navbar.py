import customtkinter as ctk
from app.utils.selection import populate_selection_manager, SelectionManager
from src.config import config
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pages.page import Page


class SelectorFrame(ctk.CTkFrame):

    def __init__(self, master, page_name: str):
        super().__init__(master, fg_color="transparent")
        self.page_name = page_name


class Navbar(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master, fg_color="transparent", height=32)
        self.master = master

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

        populate_selection_manager(
            SelectionManager(),
            frames=selector_frames,
            default_frame=default_frame,
            on_select=lambda frame: self.master.select_page(frame.page_name),
        )
