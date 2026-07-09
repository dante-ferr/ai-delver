import customtkinter as ctk
from loaders import level_loader
from typing import TYPE_CHECKING
from ._canvas_click_handler import CanvasClickHandler
from ._canvas_scroller import CanvasScroller
from ._canvas_camera import CanvasCamera
from ._canvas_grid_element_renderer import CanvasGridElementRenderer
from ._canvas_overlay import CanvasOverlay

if TYPE_CHECKING:
    from pytiling import Direction, GridMap


class LevelCanvas(ctk.CTkCanvas):
    """
    The main canvas widget for the level editor.

    This class is the core of the visual editor, responsible for displaying the
    level grid, tiles, objects, and overlays. It manages zooming, scrolling,
    and dispatches events to its various handler components (renderer, click handler,
    scroller, overlay).
    """

    def __init__(self, master):
        super().__init__(master, highlightthickness=0)

        self.configure(bg="black")

        self._add_event_listeners()

        self.camera = CanvasCamera(self)

        self.click_handler = CanvasClickHandler(self)
        self.grid_element_renderer = CanvasGridElementRenderer(self)
        self.overlay = CanvasOverlay(self)
        self.scroller = CanvasScroller(self)

        self.refresh()

    @property
    def zoom_level(self) -> int:
        """The current magnification level of the canvas."""
        return self.camera.zoom_level

    def set_zoom_level(self, value: int, origin_x: int, origin_y: int):
        """
        Sets the zoom level by re-rendering and repositioning existing canvas items
        relative to a given origin point.
        """
        if abs(value - self.camera.zoom_level) < 1e-9:
            return

        old_zoom = self.camera.zoom_level
        self.camera.set_zoom_level(value)

        # Rescale and reposition all existing image-based grid elements.
        for item_id in self.find_withtag("grid_element"):
            self.grid_element_renderer.rescale_and_reposition_item(
                item_id, old_zoom, origin_x, origin_y
            )

        # Redraw non-image overlays like grid lines and borders
        self.overlay.refresh()

    def _add_event_listeners(self):
        """Binds canvas methods to events from the underlying level map data model."""
        level_loader.level.map.events["expanded"].connect(
            self._expansion_callback, weak=True
        )
        level_loader.level.map.events["reducted"].connect(
            self._reduction_callback, weak=True
        )

    def _expansion_callback(
        self,
        sender,
        direction: "Direction",
        size: int,
        new_positions: "GridMap.NewPositions",
    ):
        """
        Callback for when the level map is expanded. It shifts the drawing offset
        if the expansion is on the top or left, to keep the existing map in place.
        """
        self.camera.handle_expansion(direction, size)

        self.overlay.handle_expansion(new_positions)
        self._on_map_size_change()

    def _reduction_callback(
        self,
        sender,
        direction: "Direction",
        size: int,
        removed_positions: "GridMap.RemovedPositions",
    ):
        """
        Callback for when the level map is reduced. It handles removing visual
        elements and shifting the drawing offset if necessary.
        """
        self.grid_element_renderer.handle_reduction(removed_positions)
        self.overlay.handle_reduction(removed_positions)
        self.camera.handle_reduction(direction, size)

        self._on_map_size_change()

    def _on_map_size_change(self):
        self.overlay.draw_border()

    def refresh(self):
        """Performs a full redraw of all canvas elements."""
        self.grid_element_renderer.erase_all_grid_elements()
        self.grid_element_renderer.draw_all_grid_elements()

        self.overlay.refresh()

    def update_draw_order(self):
        """Ensure layers are drawn in the correct Z-index order."""
        layers = level_loader.level.map.layers

        for layer in layers:
            tag = f"layer={layer.name}"
            self.tag_raise(tag)
        self.tag_raise("line")
        self.tag_raise("border")

    def items_with_tags(self, *tags):
        """
        Finds all canvas items that have *all* of the specified tags.
        This is an alternative to `find_withtag` which uses an AND condition
        instead of OR.
        """
        if not tags:
            return []

        items_with_all_tags = set(self.find_withtag(tags[0]))

        for tag in tags[1:]:
            items_with_all_tags &= set(self.find_withtag(tag))

        return list(items_with_all_tags)

    def canvas_to_world_grid_pos(self, coords: tuple[int, int]) -> tuple[int, int]:
        """
        Delegates coordinate conversion to the camera.
        """
        return self.camera.canvas_to_world_grid_pos(coords)

    def world_to_canvas_grid_pos(self, coords: tuple[int, int]) -> tuple[int, int]:
        """
        Delegates coordinate conversion to the camera.
        """
        return self.camera.world_to_canvas_grid_pos(coords)

    @property
    def grid_draw_offset(self):
        """The drawing offset in grid units."""
        return self.camera.grid_draw_offset

    @property
    def zoomed_draw_offset(self):
        """The drawing offset in pixels, adjusted for the current zoom level."""
        return self.camera.zoomed_draw_offset

    @property
    def grid_lines(self):
        """Whether grid lines should be visible, based on the global state."""
        from state_managers import canvas_state_manager

        return canvas_state_manager.get_value("grid_lines")

    @property
    def map_size(self):
        """The total size of the map in pixels, adjusted for zoom."""
        return (
            level_loader.level.map.size[0] * self.zoom_level,
            level_loader.level.map.size[1] * self.zoom_level,
        )

    @property
    def tile_size(self):
        """The current tile size in pixels, adjusted for zoom level."""
        return self.camera.tile_size
