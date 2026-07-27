import customtkinter as ctk
from src.config import config


class TitleTextbox(ctk.CTkTextbox):

    def __init__(self, master, default_text=""):
        super().__init__(
            master,
            height=4,
            wrap="none",
            font=ctk.CTkFont(size=config.STYLE.FONT.STANDARD_SIZE),
        )

        self._name = default_text
        self._dirty = False
        self._syncing = False
        self._render()
        self.bind("<KeyRelease>", self._update_name)

    def _get_input(self):
        """Get the current text from the textbox (dirty marker stripped)."""
        text = self.get("0.0", "end").strip()
        if text.startswith("*"):
            text = text[1:].strip()
        return text

    def _render(self):
        self._syncing = True
        try:
            if self._dirty and self._name:
                display = f"* {self._name}"
            elif self._dirty:
                display = "*"
            else:
                display = self._name
            self.delete("0.0", "end")
            self.insert("0.0", display)
        finally:
            self._syncing = False

    def set_dirty(self, dirty: bool):
        dirty = bool(dirty)
        if dirty == self._dirty:
            return
        self._name = self._get_input() or self._name
        self._dirty = dirty
        self._render()

    def set_name(self, name: str, *, dirty: bool | None = None):
        self._name = name
        if dirty is not None:
            self._dirty = bool(dirty)
        self._render()

    def _update_name(self, event=None):
        """Update the underlying name. Must be overridden in subclasses."""
        if self._syncing:
            return
        self._name = self._get_input()
