from loaders import level_loader
from src.config import config
import customtkinter as ctk
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from .level_canvas import LevelCanvas


class CanvasScroller:
    def __init__(self, canvas: "LevelCanvas"):
        self.canvas = canvas
        self.canvas.after(1, self._center_canvas)

        self.last_x: int = 0
        self.last_y: int = 0

        self.scrolling = False

        self.min_zoom = config.MIN_CANVAS_ZOOM
        self.max_zoom = config.MAX_CANVAS_ZOOM
        self._execute_zoom(config.INITIAL_CANVAS_ZOOM)

        self._bind_scroll_events()
        self.canvas.bind("<Configure>", self._on_resize)

    def _bind_scroll_events(self):
        from state_managers import canvas_state_manager

        canvas_state_manager.add_callback("zoom", self._execute_zoom)

        self.canvas.bind("<ButtonPress-3>", self._start_scroll)
        self.canvas.bind("<B3-Motion>", self._on_scroll)
        self.canvas.bind("<ButtonRelease-3>", self._stop_scroll)
        # For Windows and MacOS
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        # For Linux
        self.canvas.bind("<Button-4>", self._on_mouse_wheel)
        self.canvas.bind("<Button-5>", self._on_mouse_wheel)

    def _on_resize(self, event):
        """Handle window resizing."""
        self.canvas.update_idletasks()
        self._center_canvas()

    def _start_scroll(self, event):
        """Start scrolling when the right mouse button is pressed."""
        self.scrolling = True
        self.scroll_start_x = event.x - self.last_x
        self.scroll_start_y = event.y - self.last_y

    def _on_scroll(self, event):
        """Scroll the canvas based on mouse movement."""
        if self.scrolling:
            scroll_x = int(event.x - self.scroll_start_x)
            scroll_y = int(event.y - self.scroll_start_y)
            scroll_x, scroll_y = self._clamped_scroll_position(scroll_x, scroll_y)

            self.canvas.scan_dragto(scroll_x, scroll_y, gain=1)
            self.last_x = scroll_x
            self.last_y = scroll_y

    def _clamped_scroll_position(self, x: int, y: int) -> tuple[int, int]:
        """Clamp the scroll position to the canvas boundaries."""
        zoom = self.canvas.zoom_level

        map_origin_x, map_origin_y = self.canvas.zoomed_draw_offset

        canvas_width, canvas_height = self.canvas_size
        map_pixel_width, map_pixel_height = (
            level_loader.level.map.size[0] * zoom,
            level_loader.level.map.size[1] * zoom,
        )

        # Calculate boundaries to ensure map corners don't pass the canvas center.
        min_x = -map_origin_x - map_pixel_width + canvas_width // 2
        max_x = -map_origin_x + canvas_width // 2
        min_y = -map_origin_y - map_pixel_height + canvas_height // 2
        max_y = -map_origin_y + canvas_height // 2

        x = int(max(min_x, min(max_x, x)))
        y = int(max(min_y, min(max_y, y)))

        return x, y

    def _center_canvas(self):
        canvas_width, canvas_height = self.canvas_size
        level_width, level_height = level_loader.level.map.size
        canvas_center_x = canvas_width // 2 - level_width // 2
        canvas_center_y = canvas_height // 2 - level_height // 2

        self.canvas.scan_dragto(canvas_center_x, canvas_center_y, gain=1)
        self.last_x = canvas_center_x
        self.last_y = canvas_center_y

    def _on_mouse_wheel(self, event):
        """Handle mouse wheel: Shift adjusts brush size, otherwise zoom."""
        from state_managers import canvas_state_manager

        # Tk Shift mask (0x0001) — used for brush size instead of zoom.
        if event.state & 0x0001:
            delta = 0
            if event.num == 5 or event.delta < 0:
                delta = -1
            elif event.num == 4 or event.delta > 0:
                delta = 1
            if delta == 0:
                return

            size = int(round(float(canvas_state_manager.get_value("brush_size")))) + delta
            size = max(config.MIN_BRUSH_SIZE, min(config.MAX_BRUSH_SIZE, size))
            canvas_state_manager.set_value("brush_size", size)
            return

        zoom = -1
        if event.num == 5 or event.delta < 0:
            # Scroll down, zoom out
            zoom = self.canvas.zoom_level - 1
        elif event.num == 4 or event.delta > 0:
            # Scroll up, zoom in
            zoom = self.canvas.zoom_level + 1

        if zoom != -1:
            self._execute_zoom(zoom, origin=(event.x, event.y))
            canvas_state_manager.set_value("zoom", zoom)

    def _execute_zoom(self, new_zoom, origin: tuple[int, int] | None = None):
        """Clamp and apply zoom, keeping ``origin`` (viewport px) stable.

        ``origin`` defaults to the canvas center (e.g. zoom slider). Wheel zoom
        passes the mouse position so the level scales toward the cursor.
        """
        new_zoom = max(self.min_zoom, min(self.max_zoom, new_zoom))
        old_zoom = self.canvas.zoom_level
        if new_zoom == old_zoom:
            return

        if origin is None:
            origin = (
                self.canvas.winfo_width() // 2,
                self.canvas.winfo_height() // 2,
            )

        # Content coordinate currently under the zoom origin.
        content_x = self.canvas.canvasx(origin[0])
        content_y = self.canvas.canvasy(origin[1])
        scale = new_zoom / old_zoom

        self.canvas.set_zoom_level(new_zoom, 0, 0)

        # After absolute zoom, that content point sits at content * scale.
        # Pan so it still appears under the same viewport pixel.
        # With scan_dragto, canvasx(screen) ≈ screen - last_x.
        new_last_x = int(round(origin[0] - content_x * scale))
        new_last_y = int(round(origin[1] - content_y * scale))
        new_last_x, new_last_y = self._clamped_scroll_position(new_last_x, new_last_y)
        self.canvas.scan_dragto(new_last_x, new_last_y, gain=1)
        self.last_x = new_last_x
        self.last_y = new_last_y

    @property
    def canvas_size(self):
        return (self.canvas.winfo_width(), self.canvas.winfo_height())

    def _stop_scroll(self, event):
        """Stop scrolling when the right mouse button is released."""
        self.scrolling = False
