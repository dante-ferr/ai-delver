import customtkinter as ctk
from .sidebar import Sidebar
from .level_canvas import LevelCanvas
from .. import Page


class LevelEditor(Page):

    def __init__(self, master):
        super().__init__(master, "Level Editor")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=256)

        left_frame = ctk.CTkFrame(self, fg_color="transparent")
        left_frame.grid(row=0, column=0, sticky="nsew")
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(0, weight=0)
        left_frame.grid_rowconfigure(1, weight=1)

        canvas = LevelCanvas(left_frame)
        canvas.grid(row=1, column=0, sticky="nsew")

        sidebar = Sidebar(self)
        sidebar.grid(row=0, column=1, sticky="ns", padx=16, pady=32)

        self._bind_tool_shortcuts()

    def _bind_tool_shortcuts(self):
        root = self.winfo_toplevel()
        root.bind("<KeyPress-d>", self._select_pencil_tool, add="+")
        root.bind("<KeyPress-D>", self._select_pencil_tool, add="+")
        root.bind("<KeyPress-e>", self._select_eraser_tool, add="+")
        root.bind("<KeyPress-E>", self._select_eraser_tool, add="+")

    def _select_pencil_tool(self, _event):
        if not self._tool_shortcuts_active():
            return
        from .level_editor_manager import level_editor_manager

        if level_editor_manager.tools_frame is not None:
            level_editor_manager.tools_frame.select_tool("pencil")

    def _select_eraser_tool(self, _event):
        if not self._tool_shortcuts_active():
            return
        from .level_editor_manager import level_editor_manager

        if level_editor_manager.tools_frame is not None:
            level_editor_manager.tools_frame.select_tool("eraser")

    def _tool_shortcuts_active(self) -> bool:
        if not self.winfo_ismapped():
            return False

        focused = self.focus_get()
        while focused is not None:
            if isinstance(focused, (ctk.CTkEntry, ctk.CTkTextbox)):
                return False
            class_name = focused.winfo_class()
            if class_name in ("Entry", "Text", "TEntry"):
                return False
            focused = getattr(focused, "master", None)
        return True
