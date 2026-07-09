from loaders import level_loader
import customtkinter as ctk
from .pages.level_editor import LevelEditor
from .pages.agent import AgentPage
from .pages import Page
from .navbar import Navbar
from .theme import theme


ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme(str(theme.path))

PAGE_COMPONENTS = {
    "level_editor": LevelEditor,
    "agent": AgentPage,
}


class App(ctk.CTk):

    def __init__(self):
        from state_managers import initialize_all_state_managers

        super().__init__()
        initialize_all_state_managers()

        self.title("Ai Delver")
        self.attributes("-zoomed", True)
        self.minsize(width=800, height=600)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        self.navbar = Navbar(self)
        self.navbar.grid(row=0, column=0, sticky="ew")

        self.page_container = ctk.CTkFrame(self, fg_color="transparent")
        self.page_container.grid(row=1, column=0, sticky="nsew")
        self.page_container.grid_rowconfigure(0, weight=1)
        self.page_container.grid_columnconfigure(0, weight=1)

        self.selected_page_name: str | None = None
        self.selected_page: Page | None = None
        self._create_pages()

        self.bind("<Button-1>", self.clear_focus)

        self._try_to_connect_to_server()

    def _try_to_connect_to_server(self):
        from client_requests import client_requester
        import threading
        import asyncio

        async def _connect():
            response = await client_requester.initial_request()

            if not response:
                self.after(
                    5000,
                    lambda: threading.Thread(
                        target=lambda: asyncio.run(_connect()), daemon=True
                    ).start(),
                )

        self.after(
            100,
            lambda: threading.Thread(
                target=lambda: asyncio.run(_connect()), daemon=True
            ).start(),
        )

    def restart_page(self, page_name: str):
        if self.pages[page_name]:
            self.pages[page_name].pack_forget()
            self.pages[page_name].grid_forget()
        self.pages[page_name] = PAGE_COMPONENTS[page_name](self.page_container)

        if self.selected_page_name == page_name:
            self.select_page(page_name)

    def restart_all_pages(self):
        for page_name in self.pages.keys():
            self.restart_page(page_name)

    def _create_pages(self):
        self.pages: dict[str, Page] = {
            name: component(self.page_container)
            for name, component in PAGE_COMPONENTS.items()
        }
        self.navbar.create_page_selectors(self.pages, default_page_name="level_editor")

    def select_page(self, page_name: str):
        page = self.pages[page_name]

        if self.selected_page is not None:
            self.selected_page.grid_forget()

        self.selected_page_name = page_name
        self.selected_page = page

        page.grid(row=0, column=0, sticky="nsew")

    def clear_focus(self, event):
        widget_under_cursor = self.winfo_containing(event.x_root, event.y_root)

        parent_ctk_widget = self.get_parent_ctk_widget(widget_under_cursor)

        if parent_ctk_widget is None or not self.is_focusable(parent_ctk_widget):
            self.focus_set()

    def get_parent_ctk_widget(self, widget):
        """
        Traverse up the widget hierarchy to find the parent CTk widget.
        """
        while widget is not None:
            if isinstance(widget, (ctk.CTkBaseClass, ctk.CTk)):
                return widget
            widget = widget.master
        return None

    def is_focusable(self, widget):
        """
        Check if the widget is focusable (e.g., CTkEntry, CTkTextbox, CTkButton, etc.).
        """
        focusable_widgets = (
            ctk.CTkEntry,
            ctk.CTkTextbox,
            ctk.CTkButton,
        )
        return isinstance(widget, focusable_widgets)

    @property
    def level(self):
        return level_loader.level
