import customtkinter as ctk
from .canvas_objects_panel import CanvasObjectsPanel
from typing import cast
from ...level_editor_manager import level_editor_manager


class CanvasObjectPanelsWrapper(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        self.current_canvas_objects_panel: CanvasObjectsPanel | None = None
        self.canvas_objects_panels = self._create_canvas_objects_panels()

        # Initial selection
        current_layer = level_editor_manager.selector.get_selection("layer")
        self._set_current_canvas_objects_panel_by_layer_name(current_layer)

        level_editor_manager.selector.set_select_callback(
            "layer", self._on_layer_select
        )

    def _create_canvas_objects_panels(self):
        canvas_objects_panels: dict[str, CanvasObjectsPanel] = {}

        for layer in level_editor_manager.objects_manager.layers:
            # Passing max_height/height to control the scrollable area size
            panel = CanvasObjectsPanel(self, layer.name, height=400)
            canvas_objects_panels[layer.name] = panel

        return canvas_objects_panels

    def _on_layer_select(self, layer_name: str):
        self._set_current_canvas_objects_panel_by_layer_name(layer_name)

        current_canvas_objects_panel = cast(
            CanvasObjectsPanel, self.current_canvas_objects_panel
        )

        # Trigger visibility check when showing the panel to ensure scrollbar state is correct
        current_canvas_objects_panel._check_scroll_visibility()

        # Adjust wrapper height if necessary (though pack fill usually handles this)
        self.configure(height=current_canvas_objects_panel.winfo_reqheight())

    def _set_current_canvas_objects_panel_by_layer_name(self, layer_name: str):
        if self.current_canvas_objects_panel is not None:
            self.current_canvas_objects_panel.pack_forget()

        self.current_canvas_objects_panel = self.canvas_objects_panels[layer_name]
        self.current_canvas_objects_panel.pack(
            pady=8, anchor="w", fill="both", expand=True
        )
