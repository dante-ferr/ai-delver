from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .level_canvas import LevelCanvas
    from pytiling import GridMap


class CanvasOverlay:
    def __init__(self, canvas: "LevelCanvas"):
        from state_managers import canvas_state_manager

        self.canvas = canvas

        canvas_state_manager.add_callback("grid_lines", self._handle_grid_lines_toggle)

    def _handle_grid_lines_toggle(self, value: bool):
        """Handle the grid lines toggle."""
        if value:
            self.draw_grid_lines()
        else:
            self.canvas.delete("line")

    def handle_expansion(self, new_positions: "GridMap.NewPositions"):
        for position in new_positions:
            self.draw_tile_lines(position)

    def handle_reduction(self, removed_positions: "GridMap.RemovedPositions"):
        for position in removed_positions:
            self.erase_tile_lines(position)

    def draw_grid_lines(self):
        """Draw grid lines on the canvas using micro lines per tile."""
        from loaders import level_loader

        if not self.grid_lines_activated:
            return

        self.canvas.delete("line")

        grid_width, grid_height = level_loader.level.map.grid_size

        for grid_x in range(0, grid_width):
            for grid_y in range(0, grid_height):
                self.draw_tile_lines((grid_x, grid_y))

    def draw_tile_lines(self, grid_pos: tuple[int, int]):
        """Draw micro lines around a tile."""
        if not self.grid_lines_activated:
            return

        tile_width, tile_height = self.canvas.tile_size
        offset_x, offset_y = self.canvas.camera.zoomed_draw_offset

        grid_x, grid_y = grid_pos
        x = grid_x * tile_width
        y = grid_y * tile_height
        canvas_grid_x, canvas_grid_y = self.canvas.camera.world_to_canvas_grid_pos(
            (grid_x, grid_y)
        )

        # Vertical line (left of the tile)
        self.canvas.create_line(
            x + offset_x,
            y + offset_y,
            x + offset_x,
            y + tile_height + offset_y,
            fill="gray",
            tags=("line", f"{canvas_grid_x},{canvas_grid_y}"),
        )

        # Horizontal line (top of the tile)
        self.canvas.create_line(
            x + offset_x,
            y + offset_y,
            x + tile_width + offset_x,
            y + offset_y,
            fill="gray",
            tags=("line", f"{canvas_grid_x},{canvas_grid_y}"),
        )

    @property
    def grid_lines_activated(self):
        from state_managers import canvas_state_manager

        return canvas_state_manager.get_value("grid_lines")

    def erase_tile_lines(self, grid_pos: tuple[int, int]):
        """Erase micro lines around a tile."""
        canvas_grid_x, canvas_grid_y = self.canvas.camera.world_to_canvas_grid_pos(
            grid_pos
        )

        self.canvas.delete(f"{canvas_grid_x},{canvas_grid_y}")

    def draw_border(self):
        """Draw borders on the canvas."""
        self.canvas.delete("border")

        map_width, map_height = self.canvas.map_size
        self.canvas.create_rectangle(
            self.canvas.camera.zoomed_draw_offset[0],
            self.canvas.camera.zoomed_draw_offset[1],
            map_width + self.canvas.camera.zoomed_draw_offset[0],
            map_height + self.canvas.camera.zoomed_draw_offset[1],
            outline="gray",
            width=2,
            tags="border",
        )

    def refresh(self):
        from state_managers import canvas_state_manager

        if canvas_state_manager.get_value("grid_lines"):
            self.draw_grid_lines()
        else:
            self.canvas.delete("line")
        self.draw_border()
