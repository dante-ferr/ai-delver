from pyglet import window
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from runtime.world_objects.entities.delver import Delver


class ViewControls:
    keys: window.key.KeyStateHandler

    def __init__(self, keys: window.key.KeyStateHandler):
        self.keys = keys

    def append_camera(self, camera):
        self.camera = camera

    def append_delver(self, delver: "Delver"):
        self.delver = delver

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        self._handle_zoom(scroll_y)

    def _handle_zoom(self, scroll_y):
        if not self.camera:
            raise ValueError("Camera not set")
        self.camera.scroll_zoom(scroll_y)

    def update(self, dt):
        pass
