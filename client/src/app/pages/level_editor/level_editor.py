import customtkinter as ctk
from .sidebar import Sidebar
from .level_canvas import LevelCanvas
from .. import Page


class LevelEditor(Page):
    DEBOUNCE_MS = 80
    NARROW_ASPECT_RATIO = 1.05
    NARROW_MIN_WIDTH = 750

    def __init__(self, master):
        super().__init__(master, "Level Editor")

        self._configure_after_id: str | None = None
        self._current_mode: str | None = None

        self.left_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.left_frame.grid_columnconfigure(0, weight=1)
        self.left_frame.grid_rowconfigure(0, weight=0)
        self.left_frame.grid_rowconfigure(1, weight=1)

        self.canvas = LevelCanvas(self.left_frame)
        self.canvas.grid(row=1, column=0, sticky="nsew")

        self.sidebar = Sidebar(self)

        self._bind_tool_shortcuts()

        self.bind("<Configure>", self._on_configure, add="+")
        self.after(0, self._apply_layout)

    def _on_configure(self, _event=None):
        if self._configure_after_id is not None:
            try:
                self.after_cancel(self._configure_after_id)
            except Exception:
                pass
        self._configure_after_id = self.after(self.DEBOUNCE_MS, self._apply_layout)

    def _apply_layout(self):
        self._configure_after_id = None
        width = self.winfo_width()
        height = self.winfo_height()

        if width <= 1 or height <= 1:
            return

        aspect_ratio = width / max(height, 1)
        is_narrow = aspect_ratio < self.NARROW_ASPECT_RATIO or width < self.NARROW_MIN_WIDTH
        mode = "bottom" if is_narrow else "side"

        if mode == self._current_mode:
            return
        self._current_mode = mode

        self.left_frame.grid_forget()
        self.sidebar.grid_forget()

        for r in (0, 1):
            self.grid_rowconfigure(r, weight=0, minsize=0)
        for c in (0, 1):
            self.grid_columnconfigure(c, weight=0, minsize=0)

        if mode == "side":
            self.grid_rowconfigure(0, weight=1)
            self.grid_columnconfigure(0, weight=1)
            self.grid_columnconfigure(1, weight=0, minsize=256)

            self.left_frame.grid(row=0, column=0, sticky="nsew")
            self.sidebar.grid(row=0, column=1, sticky="ns", padx=16, pady=32)
            self.sidebar.set_mode("side")
        else:
            self.grid_rowconfigure(0, weight=1)
            self.grid_rowconfigure(1, weight=0, minsize=0)
            self.grid_columnconfigure(0, weight=1)

            self.left_frame.grid(row=0, column=0, sticky="nsew")
            self.sidebar.grid(row=1, column=0, sticky="ew", padx=16, pady=(8, 16))
            self.sidebar.set_mode("bottom")

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
