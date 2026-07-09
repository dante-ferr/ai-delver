from typing import TYPE_CHECKING
from loaders import level_loader
from pytiling import Direction, direction_vectors, opposite_directions

if TYPE_CHECKING:
    from .level_canvas import LevelCanvas

# TODO: Remove the offset logic from here

class CanvasCamera:
    """
    Manages the viewport's position (pan) and scale (zoom) for the LevelCanvas.

    This class encapsulates all the logic for zooming, panning, and converting
    coordinates between the world (model) and canvas (view) space. It does not
    perform any drawing itself but provides the necessary transformations for
    the renderer.
    """

    def __init__(self, canvas: "LevelCanvas"):
        self.canvas = canvas
        self._zoom_level = 1
        self._grid_draw_offset: tuple[int, int] = (0, 0)

    @property
    def zoom_level(self) -> int:
        """The current magnification level of the canvas."""
        return self._zoom_level

    def set_zoom_level(self, value: int):
        """Sets the zoom level, clamping it to a minimum of 1."""
        if value < 1:
            value = 1
        if abs(value - self._zoom_level) < 1e-9:
            return

        self._zoom_level = value

    def shift_offset_towards(self, direction: Direction, size: int):
        """Adjusts the grid drawing offset by a given size in a specific direction."""
        self._grid_draw_offset = (
            self._grid_draw_offset[0] + direction_vectors[direction][0] * size,
            self._grid_draw_offset[1] + direction_vectors[direction][1] * size,
        )

    def handle_expansion(self, direction: Direction, size: int):
        """
        Shifts the drawing offset if the expansion is on the top or left,
        to keep the existing map in place.
        """
        if direction in ("top", "left"):
            self.shift_offset_towards(direction, size)

    def handle_reduction(self, direction: Direction, size: int):
        """
        Shifts the drawing offset if the reduction is on the top or left.
        """
        if direction in ("top", "left"):
            self.shift_offset_towards(opposite_directions[direction], size)

    def canvas_to_world_grid_pos(self, coords: tuple[int, int]) -> tuple[int, int]:
        """
        Converts grid coordinates from the canvas's relative space to the
        level map's absolute world space, accounting for the `_grid_draw_offset`.
        """
        return (
            coords[0] - self._grid_draw_offset[0],
            coords[1] - self._grid_draw_offset[1],
        )

    def world_to_canvas_grid_pos(self, coords: tuple[int, int]) -> tuple[int, int]:
        """
        Converts grid coordinates from the level map's absolute world space to
        the canvas's relative space, accounting for the `_grid_draw_offset`.
        """
        return (
            coords[0] + self._grid_draw_offset[0],
            coords[1] + self._grid_draw_offset[1],
        )

    @property
    def grid_draw_offset(self) -> tuple[int, int]:
        """The offset in grid units for drawing."""
        return self._grid_draw_offset

    @property
    def zoomed_draw_offset(self) -> tuple[int, int]:
        """The drawing offset in pixels, adjusted for the current zoom level."""
        tile_w, tile_h = self.tile_size
        return (
            self._grid_draw_offset[0] * tile_w,
            self._grid_draw_offset[1] * tile_h,
        )

    @property
    def tile_size(self) -> tuple[int, int]:
        """The current tile size in pixels, adjusted for zoom level."""
        return (
            level_loader.level.map.tile_size[0] * self.zoom_level,
            level_loader.level.map.tile_size[1] * self.zoom_level,
        )

    def calculate_zoomed_coords(
        self,
        canvas_grid_pos: tuple[int, int],
        old_zoom: int,
        origin_x: int,
        origin_y: int,
    ) -> tuple[float, float]:
        """Calculates new screen coordinates for an item relative to a zoom origin."""
        scale_factor = self.zoom_level / old_zoom
        old_tile_w = level_loader.level.map.tile_size[0] * old_zoom
        old_tile_h = level_loader.level.map.tile_size[1] * old_zoom

        old_x = canvas_grid_pos[0] * old_tile_w
        old_y = canvas_grid_pos[1] * old_tile_h

        new_x = origin_x + (old_x - origin_x) * scale_factor
        new_y = origin_y + (old_y - origin_y) * scale_factor
        return new_x, new_y
