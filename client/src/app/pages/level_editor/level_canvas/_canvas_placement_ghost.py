"""Hover ghost preview for the tile or multi-tile footprint about to be placed."""

from typing import TYPE_CHECKING, Optional
from PIL import Image, ImageTk
from loaders import level_loader
from pytiling import footprint_positions, top_left_position
from ..level_editor_manager import level_editor_manager

if TYPE_CHECKING:
    from .level_canvas import LevelCanvas
    from ..level_editor_manager.canvas_objects.canvas_object import CanvasObject


class CanvasPlacementGhost:
    """Draws a semi-transparent preview of the selected canvas object under the cursor."""

    GHOST_TAG = "placement_ghost"
    VALID_OUTLINE = "#7CFF9A"
    INVALID_OUTLINE = "#FF6B6B"
    ALPHA = 140

    def __init__(self, canvas: "LevelCanvas"):
        self.canvas = canvas
        self._photo_cache: dict[tuple[int, int, int], ImageTk.PhotoImage] = {}
        self._last_world_pos: Optional[tuple[int, int]] = None
        self._ghost_image_ref: ImageTk.PhotoImage | None = None

        # <Motion> alone does not fire while button 1 is held; bind B1-Motion too.
        self.canvas.bind("<Motion>", self._on_motion, add="+")
        self.canvas.bind("<B1-Motion>", self._on_motion, add="+")
        self.canvas.bind("<Leave>", self._on_leave, add="+")

    def clear(self):
        self.canvas.delete(self.GHOST_TAG)
        self._last_world_pos = None
        self._ghost_image_ref = None

    def refresh(self):
        """Redraw ghost at the last known position (e.g. after zoom)."""
        if self._last_world_pos is not None:
            self._draw_at(self._last_world_pos)

    def _on_leave(self, _event):
        self.clear()

    def _on_motion(self, event):
        canvas_grid_pos = self._canvas_grid_from_mouse((event.x, event.y))
        if canvas_grid_pos is None:
            self.clear()
            return

        world_pos = self.canvas.camera.canvas_to_world_grid_pos(canvas_grid_pos)
        if world_pos == self._last_world_pos:
            return
        self._draw_at(world_pos)

    def _canvas_grid_from_mouse(
        self, mouse_position: tuple[int, int]
    ) -> Optional[tuple[int, int]]:
        canvas_x = self.canvas.canvasx(mouse_position[0])
        canvas_y = self.canvas.canvasy(mouse_position[1])
        tile_width, tile_height = level_loader.level.map.tile_size
        zoom = self.canvas.camera.zoom_level
        return (
            int(canvas_x // (tile_width * zoom)),
            int(canvas_y // (tile_height * zoom)),
        )

    def _selected_canvas_object(self) -> "CanvasObject | None":
        try:
            layer_name = level_editor_manager.selector.get_selection("layer")
            object_name = level_editor_manager.selector.get_selection(
                f"{layer_name}.canvas_object"
            )
            tool = level_editor_manager.selector.get_selection("tool")
        except Exception:
            return None

        if tool != "pencil" or not object_name:
            return None

        try:
            return level_editor_manager.objects_manager.get_canvas_object(
                str(object_name)
            )
        except KeyError:
            return None

    def _selected_layer_name(self) -> str | None:
        try:
            return str(level_editor_manager.selector.get_selection("layer"))
        except Exception:
            return None

    def _footprint_is_valid(
        self,
        world_pos: tuple[int, int],
        size: tuple[int, int],
        layer_name: str | None,
    ) -> bool:
        """True when the footprint is in-bounds and clear of locked tiles/elements.

        Mirrors ``GridLayer.add_element``: locked same-layer or concurrent-layer
        elements (e.g. sealed map-edge platform tiles) block placement.
        """
        grid_map = level_loader.level.map
        footprint = footprint_positions(world_pos, size)
        for cell in footprint:
            if not grid_map.position_is_valid(cell):
                return False

        if not layer_name:
            return True

        layer = grid_map.get_layer(layer_name)
        if layer is None:
            return True

        for cell in footprint:
            same_layer_element = layer.get_element_at(cell)
            if same_layer_element is not None and same_layer_element.locked:
                return False
            for concurrent_layer in layer.concurrent_layers:
                concurrent_element = concurrent_layer.get_element_at(cell)
                if concurrent_element is not None and concurrent_element.locked:
                    return False
        return True

    def _draw_at(self, world_pos: tuple[int, int]):
        self.canvas.delete(self.GHOST_TAG)
        self._last_world_pos = world_pos

        canvas_object = self._selected_canvas_object()
        if canvas_object is None:
            self.clear()
            return

        size = canvas_object.size
        layer_name = self._selected_layer_name()
        if not self._footprint_is_valid(world_pos, size, layer_name):
            self._draw_invalid_outline(world_pos, size)
            return

        pil_image = canvas_object.image
        ghost_pil = pil_image.convert("RGBA")
        alpha = ghost_pil.split()[3].point(lambda p: min(p, self.ALPHA))
        ghost_pil.putalpha(alpha)

        tile_w, tile_h = level_loader.level.map.tile_size
        zoom = self.canvas.camera.zoom_level
        scaled = (
            max(1, int(tile_w * size[0] * zoom)),
            max(1, int(tile_h * size[1] * zoom)),
        )
        cache_key = (id(pil_image), scaled[0], scaled[1])
        photo = self._photo_cache.get(cache_key)
        if photo is None:
            resized = ghost_pil.resize(scaled, Image.NEAREST)  # type: ignore
            photo = ImageTk.PhotoImage(resized)
            self._photo_cache[cache_key] = photo
        self._ghost_image_ref = photo

        top_left = top_left_position(world_pos, size)
        canvas_grid = self.canvas.camera.world_to_canvas_grid_pos(top_left)
        screen_tile_w, screen_tile_h = self.canvas.tile_size
        screen_x = canvas_grid[0] * screen_tile_w
        screen_y = canvas_grid[1] * screen_tile_h

        self.canvas.create_image(
            screen_x,
            screen_y,
            image=photo,
            anchor="nw",
            tags=(self.GHOST_TAG,),
        )
        self._draw_outline(world_pos, size, self.VALID_OUTLINE)
        self.canvas.tag_raise(self.GHOST_TAG)

    def _draw_invalid_outline(
        self, world_pos: tuple[int, int], size: tuple[int, int]
    ):
        self._draw_outline(world_pos, size, self.INVALID_OUTLINE)

    def _draw_outline(
        self,
        world_pos: tuple[int, int],
        size: tuple[int, int],
        color: str,
    ):
        top_left = top_left_position(world_pos, size)
        canvas_grid = self.canvas.camera.world_to_canvas_grid_pos(top_left)
        tile_w, tile_h = self.canvas.tile_size
        x0 = canvas_grid[0] * tile_w
        y0 = canvas_grid[1] * tile_h
        x1 = x0 + size[0] * tile_w
        y1 = y0 + size[1] * tile_h
        self.canvas.create_rectangle(
            x0,
            y0,
            x1,
            y1,
            outline=color,
            width=2,
            tags=(self.GHOST_TAG,),
        )
