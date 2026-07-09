import customtkinter as ctk
import platform

class MouseWheelScrollableFrame(ctk.CTkScrollableFrame):
    """
    A CTkScrollableFrame that supports:
    1. Cross-platform mouse wheel scrolling (Windows, macOS, Linux).
    2. Recursive scroll binding (children inherit scroll behavior).
    3. Auto-hiding scrollbar when content fits the viewport.
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self._scroll_active = True

        self._system = platform.system()
        self._scroll_events = []
        if self._system == "Linux":
            self._scroll_events = ["<Button-4>", "<Button-5>"]
        else:
            self._scroll_events = ["<MouseWheel>"]

        self.bind_scroll_events_recursively(self)
        self.bind_scroll_events_recursively(self._parent_canvas)

        self._parent_canvas.bind(
            "<Configure>", lambda e: self._check_scroll_visibility(), add="+"
        )

    def bind_scroll_events_recursively(self, widget):
        """
        Binds scroll events to the widget and all its current children.
        Use this method when adding complex custom widgets to the frame.
        """
        self._bind_to_widget(widget)

        for child in widget.winfo_children():
            self.bind_scroll_events_recursively(child)

    def _bind_to_widget(self, widget):
        for event_str in self._scroll_events:
            widget.bind(event_str, self.on_mouse_wheel, add="+")

    def on_mouse_wheel(self, event):
        if not self._scroll_active:
            return

        if self._system == "Linux":
            if event.num == 4:
                self._parent_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self._parent_canvas.yview_scroll(1, "units")
        else:
            # CTk/Tkinter usually handles delta differently.
            # Negative delta is down on Windows.
            direction = -1 if event.delta > 0 else 1
            self._parent_canvas.yview_scroll(direction, "units")

    def _check_scroll_visibility(self):
        """
        Enables or disables scrolling/scrollbar based on content height.
        """
        self.update_idletasks()

        content_height = self.winfo_reqheight()
        viewport_height = self._parent_canvas.winfo_height()

        if content_height > viewport_height:
            if not self._scroll_active:
                self._scroll_active = True
                try:
                    self._scrollbar.grid()
                except Exception:
                    # Suppress errors if scrollbar is not ready or widget is destroyed
                    pass
        else:
            if self._scroll_active:
                self._scroll_active = False
                self._scrollbar.grid_remove()
