"""Hover ghost preview for the tile or multi-tile footprint about to be placed."""

from typing import TYPE_CHECKING, Optional
import math
from PIL import Image, ImageTk
from loaders import level_loader
from pytiling import footprint_positions, top_left_position, preview_autotile_displays
from src.utils import brush_bottom_left, brush_cells, brush_pivot
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
        from state_managers import canvas_state_manager

        self.canvas = canvas
        self._photo_cache: dict[tuple, ImageTk.PhotoImage] = {}
        self._last_continuous_world_pos: Optional[tuple[float, float]] = None
        self._last_pivot: Optional[tuple[int, int]] = None
        self._last_draw_key: tuple | None = None
        self._ghost_image_refs: list[ImageTk.PhotoImage] = []

        # <Motion> alone does not fire while button 1 is held; bind B1-Motion too.
        self.canvas.bind("<Motion>", self._on_motion, add="+")
        self.canvas.bind("<B1-Motion>", self._on_motion, add="+")
        self.canvas.bind("<Leave>", self._on_leave, add="+")

        canvas_state_manager.add_callback("brush_size", lambda _value: self.refresh())
        selector = level_editor_manager.selector
        selector.add_select_callback("tool", lambda _value: self.refresh())
        selector.add_select_callback("layer", lambda _value: self.refresh())
        for layer in level_editor_manager.objects_manager.layers:
            selector.add_select_callback(
                f"{layer.name}.canvas_object", lambda _value: self.refresh()
            )

    def clear(self):
        self.canvas.delete(self.GHOST_TAG)
        self._last_continuous_world_pos = None
        self._last_pivot = None
        self._last_draw_key = None
        self._ghost_image_refs = []

    def refresh(self):
        """Redraw ghost at the last known position (e.g. after zoom)."""
        if self._last_continuous_world_pos is not None:
            self._last_pivot = None
            self._last_draw_key = None
            self._draw_at(self._last_continuous_world_pos)

    def _on_leave(self, _event):
        self.clear()

    def _on_motion(self, event):
        continuous_canvas = self._continuous_canvas_from_mouse((event.x, event.y))
        if continuous_canvas is None:
            self.clear()
            return

        offset = self.canvas.camera.grid_draw_offset
        continuous_world = (
            continuous_canvas[0] - offset[0],
            continuous_canvas[1] - offset[1],
        )
        brush_size = self._effective_brush_size()
        pivot = brush_pivot(continuous_world, brush_size)
        draw_key = (
            pivot,
            brush_size,
            self._selected_tool(),
            self._selected_layer_name(),
            self._selected_object_name(),
        )
        if draw_key == self._last_draw_key:
            self._last_continuous_world_pos = continuous_world
            return
        self._draw_at(continuous_world)

    def _continuous_canvas_from_mouse(
        self, mouse_position: tuple[int, int]
    ) -> Optional[tuple[float, float]]:
        canvas_x = self.canvas.canvasx(mouse_position[0])
        canvas_y = self.canvas.canvasy(mouse_position[1])
        tile_width, tile_height = level_loader.level.map.tile_size
        zoom = self.canvas.camera.zoom_level
        return (
            canvas_x / (tile_width * zoom),
            canvas_y / (tile_height * zoom),
        )

    def _selected_tool(self) -> str | None:
        try:
            return str(level_editor_manager.selector.get_selection("tool"))
        except Exception:
            return None

    def _brush_size(self) -> int:
        from state_managers import canvas_state_manager
        from src.config import config

        size = int(round(float(canvas_state_manager.get_value("brush_size"))))
        return max(config.MIN_BRUSH_SIZE, min(config.MAX_BRUSH_SIZE, size))

    def _effective_brush_size(self) -> int:
        """Pencil brush size only applies on the platforms (tile) layer."""
        if self._selected_tool() == "pencil" and self._selected_layer_name() != "platforms":
            return 1
        return self._brush_size()

    def _selected_object_name(self) -> str | None:
        try:
            layer_name = level_editor_manager.selector.get_selection("layer")
            return str(
                level_editor_manager.selector.get_selection(
                    f"{layer_name}.canvas_object"
                )
            )
        except Exception:
            return None

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

    def _is_platform_layer(self) -> bool:
        return self._selected_layer_name() == "platforms"

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

    def _draw_at(self, continuous_world_pos: tuple[float, float]):
        self.canvas.delete(self.GHOST_TAG)
        self._ghost_image_refs = []
        self._last_continuous_world_pos = continuous_world_pos
        brush_size = self._effective_brush_size()
        self._last_pivot = brush_pivot(continuous_world_pos, brush_size)
        self._last_draw_key = (
            self._last_pivot,
            brush_size,
            self._selected_tool(),
            self._selected_layer_name(),
            self._selected_object_name(),
        )

        tool = self._selected_tool()

        if tool == "eraser":
            self._draw_brush_outline(continuous_world_pos, brush_size)
            self.canvas.tag_raise(self.GHOST_TAG)
            return

        if tool != "pencil":
            self.clear()
            return

        canvas_object = self._selected_canvas_object()
        if canvas_object is None:
            self.clear()
            return

        if self._is_platform_layer():
            self._draw_platform_brush_ghost(continuous_world_pos, brush_size)
            return

        world_pos = (
            math.floor(continuous_world_pos[0]),
            math.floor(continuous_world_pos[1]),
        )
        size = canvas_object.size
        layer_name = self._selected_layer_name()
        if not self._footprint_is_valid(world_pos, size, layer_name):
            self._draw_invalid_outline(world_pos, size)
            return

        self._draw_object_image_ghost(canvas_object, world_pos, size)
        self._draw_outline(world_pos, size, self.VALID_OUTLINE)
        self.canvas.tag_raise(self.GHOST_TAG)

    def _draw_platform_brush_ghost(
        self, continuous_world_pos: tuple[float, float], brush_size: int
    ):
        cells = brush_cells(continuous_world_pos, brush_size)
        bottom_left = brush_bottom_left(continuous_world_pos, brush_size)
        layer_name = self._selected_layer_name()
        valid = self._footprint_is_valid(
            bottom_left, (brush_size, brush_size), layer_name
        )

        platforms = level_loader.level.map.tilemap.get_layer("platforms")
        occupied: set[tuple[int, int]] = {
            element.position for element in platforms.elements
        }
        occupied.update(cells)

        rules = platforms.autotile_rules.get("platform") or platforms.autotile_rules.get(
            "default", []
        )
        displays = preview_autotile_displays(
            cells,
            occupied,
            level_loader.level.map.position_is_valid,
            rules,
        )

        tileset_image = self.canvas.grid_element_renderer.tileset_images[
            platforms.tileset
        ]
        zoom = self.canvas.camera.zoom_level
        tile_w, tile_h = level_loader.level.map.tile_size
        scaled = (max(1, int(tile_w * zoom)), max(1, int(tile_h * zoom)))
        screen_tile_w, screen_tile_h = self.canvas.tile_size

        for cell in cells:
            if not level_loader.level.map.position_is_valid(cell):
                continue
            display = displays.get(cell, (0, 0))
            pil_image = tileset_image.get_tile_image(display)
            if pil_image is None:
                continue

            ghost_pil = pil_image.convert("RGBA")
            alpha = ghost_pil.split()[3].point(lambda p: min(p, self.ALPHA))
            ghost_pil.putalpha(alpha)

            cache_key = ("autotile", display, scaled[0], scaled[1])
            photo = self._photo_cache.get(cache_key)
            if photo is None:
                resized = ghost_pil.resize(scaled, Image.NEAREST)  # type: ignore
                photo = ImageTk.PhotoImage(resized)
                self._photo_cache[cache_key] = photo
            self._ghost_image_refs.append(photo)

            canvas_grid = self.canvas.camera.world_to_canvas_grid_pos(cell)
            self.canvas.create_image(
                canvas_grid[0] * screen_tile_w,
                canvas_grid[1] * screen_tile_h,
                image=photo,
                anchor="nw",
                tags=(self.GHOST_TAG,),
            )

        color = self.VALID_OUTLINE if valid else self.INVALID_OUTLINE
        self._draw_outline(bottom_left, (brush_size, brush_size), color)
        self.canvas.tag_raise(self.GHOST_TAG)

    def _draw_object_image_ghost(
        self,
        canvas_object: "CanvasObject",
        world_pos: tuple[int, int],
        size: tuple[int, int],
    ):
        pil_image = canvas_object.image
        ghost_pil = pil_image.convert("RGBA")
        alpha = ghost_pil.split()[3].point(lambda p: min(p, self.ALPHA))
        ghost_pil.putalpha(alpha)

        zoom = self.canvas.camera.zoom_level
        image_fit = canvas_object.image_fit
        if image_fit == "native":
            scaled = (
                max(1, int(pil_image.width * zoom)),
                max(1, int(pil_image.height * zoom)),
            )
        else:
            tile_w, tile_h = level_loader.level.map.tile_size
            scaled = (
                max(1, int(tile_w * size[0] * zoom)),
                max(1, int(tile_h * size[1] * zoom)),
            )
        cache_key = (id(pil_image), scaled[0], scaled[1], image_fit)
        photo = self._photo_cache.get(cache_key)
        if photo is None:
            resized = ghost_pil.resize(scaled, Image.NEAREST)  # type: ignore
            photo = ImageTk.PhotoImage(resized)
            self._photo_cache[cache_key] = photo
        self._ghost_image_refs.append(photo)

        top_left = top_left_position(world_pos, size)
        canvas_grid = self.canvas.camera.world_to_canvas_grid_pos(top_left)
        screen_tile_w, screen_tile_h = self.canvas.tile_size
        footprint_x = canvas_grid[0] * screen_tile_w
        footprint_y = canvas_grid[1] * screen_tile_h
        if image_fit == "native":
            footprint_w = size[0] * screen_tile_w
            footprint_h = size[1] * screen_tile_h
            screen_x = footprint_x + (footprint_w - photo.width()) / 2
            screen_y = footprint_y + footprint_h - photo.height()
        else:
            screen_x = footprint_x
            screen_y = footprint_y

        self.canvas.create_image(
            screen_x,
            screen_y,
            image=photo,
            anchor="nw",
            tags=(self.GHOST_TAG,),
        )

    def _draw_brush_outline(
        self, continuous_world_pos: tuple[float, float], brush_size: int
    ):
        bottom_left = brush_bottom_left(continuous_world_pos, brush_size)
        size = (brush_size, brush_size)
        if self._selected_tool() == "eraser":
            in_bounds = all(
                level_loader.level.map.position_is_valid(cell)
                for cell in footprint_positions(bottom_left, size)
            )
            color = self.VALID_OUTLINE if in_bounds else self.INVALID_OUTLINE
        else:
            color = (
                self.VALID_OUTLINE
                if self._footprint_is_valid(
                    bottom_left, size, self._selected_layer_name()
                )
                else self.INVALID_OUTLINE
            )
        self._draw_outline(bottom_left, size, color)

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
