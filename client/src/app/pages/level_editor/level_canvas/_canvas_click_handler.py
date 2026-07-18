from typing import TYPE_CHECKING, Optional, cast
import math
from src.utils import brush_cells
from loaders import level_loader
from pytiling import Tile
from ..level_editor_manager import level_editor_manager

if TYPE_CHECKING:
    from .level_canvas import LevelCanvas


class CanvasClickHandler:
    """
    Manages all mouse-based interactions on the LevelCanvas, including
    clicking, dragging, and tool-based actions like drawing or erasing tiles.
    It translates mouse coordinates to grid positions and applies the
    currently selected tool's logic.
    """

    def __init__(self, canvas: "LevelCanvas"):
        self.canvas = canvas

        self.platforms = level_loader.level.map.tilemap.get_layer("platforms")

        self.drawn_tile_positions: list[tuple[int, int]] = []
        self.last_continuous_canvas_pos: tuple[float, float] | None = None

        self._bind_click_hold_events()

    def _bind_click_hold_events(self):
        """Binds mouse events to their corresponding handler methods."""
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())
        self.canvas.bind("<ButtonPress-1>", self._start_click)
        self.canvas.bind("<B1-Motion>", self._on_click_hold)
        self.canvas.bind("<ButtonRelease-1>", self._stop_click)
        self.canvas.bind("<KeyPress-i>", self._debug_inspect_tile)

    def _start_click(self, event):
        """Handles the initial mouse button press on the canvas."""
        self.drawn_tile_positions = []
        continuous_pos = self._get_continuous_canvas_grid_pos((event.x, event.y))
        if continuous_pos is None:
            return
        self.last_continuous_canvas_pos = continuous_pos
        self._process_continuous_canvas_pos(continuous_pos)

    def _on_click_hold(self, event):
        """
        Handles mouse movement while the button is held down. Samples along the
        continuous path so even brushes (crossing-pivoted) stay gap-free.
        """
        current = self._get_continuous_canvas_grid_pos((event.x, event.y))
        if current is None:
            return

        if self.last_continuous_canvas_pos is None:
            self.last_continuous_canvas_pos = current

        for pos in self._sample_continuous_line(self.last_continuous_canvas_pos, current):
            self._process_continuous_canvas_pos(pos)

        self.last_continuous_canvas_pos = current

    def _stop_click(self, event):
        """Handles the mouse button release event."""
        self.drawn_tile_positions = []
        self.last_continuous_canvas_pos = None

    def _get_continuous_canvas_grid_pos(
        self, mouse_position: tuple[int, int]
    ) -> Optional[tuple[float, float]]:
        """Canvas grid position with sub-tile precision."""
        canvas_x = self.canvas.canvasx(mouse_position[0])
        canvas_y = self.canvas.canvasy(mouse_position[1])
        tile_width, tile_height = level_loader.level.map.tile_size
        zoom = self.canvas.camera.zoom_level
        return (
            canvas_x / (tile_width * zoom),
            canvas_y / (tile_height * zoom),
        )

    def _sample_continuous_line(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        step: float = 0.25,
    ):
        x0, y0 = start
        x1, y1 = end
        dist = math.hypot(x1 - x0, y1 - y0)
        if dist < 1e-9:
            yield start
            return
        n = max(1, int(math.ceil(dist / step)))
        for i in range(n + 1):
            t = i / n
            yield (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)

    def _brush_size(self) -> int:
        from state_managers import canvas_state_manager
        from src.config import config

        size = int(round(float(canvas_state_manager.get_value("brush_size"))))
        return max(config.MIN_BRUSH_SIZE, min(config.MAX_BRUSH_SIZE, size))

    def _process_continuous_canvas_pos(self, canvas_pos: tuple[float, float]):
        """Apply the selected tool across the brush at a continuous canvas position."""
        self.selected_layer_name = level_editor_manager.selector.get_selection("layer")
        self.selected_canvas_object_name = cast(
            str,
            level_editor_manager.selector.get_selection(
                self.selected_layer_name + ".canvas_object"
            ),
        )
        self.selected_tool_name = level_editor_manager.selector.get_selection("tool")

        offset = self.canvas.camera.grid_draw_offset
        world_pos = (canvas_pos[0] - offset[0], canvas_pos[1] - offset[1])
        for cell in brush_cells(world_pos, self._brush_size()):
            if cell in self.drawn_tile_positions:
                continue
            self.drawn_tile_positions.append(cell)
            self._handle_interaction(cell)

    def _handle_interaction(self, grid_pos: tuple[int, int]):
        """
        Applies the logic for the currently selected tool ('pencil' or 'eraser')
        at the given world grid position.

        Args:
            grid_pos: The world-space grid position to interact with.
        """
        if not level_loader.level.map.position_is_valid(grid_pos):
            return

        if self.selected_tool_name == "pencil":
            canvas_object = level_editor_manager.objects_manager.get_canvas_object(
                self.selected_canvas_object_name
            )
            from pytiling import footprint_positions

            size = getattr(canvas_object, "size", (1, 1))
            for cell in footprint_positions(grid_pos, size):
                if not level_loader.level.map.position_is_valid(cell):
                    return
            canvas_object.create_element_callback(grid_pos)

        elif self.selected_tool_name == "eraser":
            layer = level_loader.level.map.get_layer(self.selected_layer_name)
            canvas_object = level_editor_manager.objects_manager.get_canvas_object(
                self.selected_canvas_object_name
            )

            if canvas_object.remove_element_callback is None:
                removed_element = layer.remove_element_at(grid_pos)
            else:
                removed_element = canvas_object.remove_element_callback(grid_pos)

            if removed_element is None:
                return

    def _debug_inspect_tile(self, event):
        """
        A debug utility to print properties of the grid element under the mouse
        cursor when the 'i' key is pressed.
        """
        continuous_pos = self._get_continuous_canvas_grid_pos((event.x, event.y))
        if continuous_pos is None:
            print("DEBUG: No canvas grid position found")
            return

        offset = self.canvas.camera.grid_draw_offset
        grid_pos = (
            math.floor(continuous_pos[0] - offset[0]),
            math.floor(continuous_pos[1] - offset[1]),
        )

        if not level_loader.level.map.position_is_valid(grid_pos):
            print("DEBUG: Invalid grid position")
            return

        selected_layer_name = level_editor_manager.selector.get_selection("layer")
        layer = level_loader.level.map.get_layer(selected_layer_name)

        if not layer:
            print(f"DEBUG: No layer found with name '{selected_layer_name}'")
            return

        element = layer.get_element_at(grid_pos)

        if isinstance(element, Tile):
            tile = cast(Tile, element)
            print(
                f"DEBUG: Tile at {grid_pos} on layer '{layer.name}': display={tile.display}"
            )
