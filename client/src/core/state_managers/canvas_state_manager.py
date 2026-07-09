import customtkinter as ctk
from .state_manager import StateManager


class CanvasStateManager(StateManager):
    """A centralized state manager for canvas-related UI properties."""

    def __init__(self):
        super().__init__()
        self.add_variable("grid_lines", ctk.BooleanVar, True)
        self.add_variable("zoom", ctk.DoubleVar, 1.0)
        self.add_variable("dynamic_resizing", ctk.BooleanVar, False)

        self._add_core_callbacks()

    def _add_core_callbacks(self):
        """Add callbacks related to core objects."""

        def _dynamic_resizing_callback(value: bool):
            from loaders import level_loader

            tilemap = level_loader.level.map.tilemap

            if value:
                tilemap.unlock_expandable_edges()
                tilemap.reduce_if_needed()
            else:
                tilemap.lock_all_edges()

        self.add_callback("dynamic_resizing", _dynamic_resizing_callback)


canvas_state_manager = CanvasStateManager()
