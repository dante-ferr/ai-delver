from runtime import Runtime
from .camera import Camera
from pyglet.window import Window
from .view_controls import ViewControls
import pyglet
from pyglet.gl import glClearColor
from typing import TYPE_CHECKING, cast
from .utils import get_average_color_from_raw_data
from pytiling.pyglet_support import TilemapRenderer
from src.config import config

if TYPE_CHECKING:
    from level.level import Level

class ViewableRuntime(Runtime):

    def __init__(self, level: "Level", physics: bool = True):
        self.camera: None | Camera = None
        self._window: Window | None = pyglet.window.Window(
            fullscreen=False, resizable=False
        )
        super().__init__(level, render=True, physics=physics)

        self.execution_speed = 1.0
        self.set_clear_color()

        def _maximize_callback(dt):
            if self._window:
                self.window.maximize()
                pyglet.clock.schedule_once(self._on_screen_maximize_interval, 0.01)

        pyglet.clock.schedule_once(_maximize_callback, 0.1)

        self.keys = pyglet.window.key.KeyStateHandler()
        self._create_controls()
        if self._window:
            self.window.push_handlers(
                self.keys,
                on_close=self._on_window_close,
            )
        self.tilemap_renderer = self.tilemap_renderer_factory()

    def tilemap_renderer_factory(self):
        tilemap_renderer = TilemapRenderer(self.level.map.tilemap)
        return tilemap_renderer

    def set_clear_color(self):
        tileset = self.level.map.get_tilemap_layer("platforms").tileset
        inner_platform_image_bytes = tileset.tile_images[3, 0]
        average_color = get_average_color_from_raw_data(
            inner_platform_image_bytes, tileset.tile_size, "RGBA"
        )
        if not average_color:
            return
        normalized_color = [c / 255.0 for c in average_color]
        glClearColor(*normalized_color, 1.0)

    def _create_controls(self):
        self.controls = ViewControls(self.keys)
        self.controls.append_delver(self.delver)

    def _on_screen_maximize_interval(self, dt):
        if not self._window:
            return
        self._lock_window_size()
        self.camera = Camera(self.window)
        self.camera.start_following(self.delver)
        self.controls.append_camera(self.camera)
        self.window.push_handlers(on_mouse_scroll=self.controls.on_mouse_scroll)

    def _on_window_close(self):
        """When the pyglet window is closed, just tell the AppManager."""
        from app_manager import app_manager
        app_manager.stop_viewable_runtimes()
        return pyglet.event.EVENT_HANDLED

    def _lock_window_size(self):
        """Locks the window size completely (even on Linux)"""
        if not self._window:
            return
        width, height = self.window.width, self.window.height
        self.window.set_minimum_size(width, height)
        self.window.set_maximum_size(width, height)
        self.window.set_size(width, height)

        @self.window.event
        def on_resize(new_width, new_height):
            if new_width != width or new_height != height:
                self.window.set_size(width, height)
            return pyglet.event.EVENT_HANDLED

    def update(self, dt):
        """Main update and drawing loop, called by pyglet's clock."""
        if self._interrupt_update_condition:
            return
        window = cast(
            Window, self._window
        )  # We know it's not None because of the previous return statement

        # Manually process window events (mouse, keyboard, close button, etc.)
        window.dispatch_events()

        if self._interrupt_update_condition:
            return

        # Update logic
        super().update(dt)
        self.controls.update(dt)

        # Drawing
        if self._window:
            self._window.clear()
        if self.camera is not None:
            with self.camera:
                self.tilemap_renderer.render_all_layers()
                self.world_objects_controller.draw_world_objects(dt)

        # Display the new frame
        window.flip()

    def run(self):
        """Schedules the update loop with pyglet's clock."""
        super().run()
        pyglet.clock.schedule_interval(self.update, 1 / float(config.FPS))

    def stop(self):
        """Un-schedules the update loop and properly closes its own window."""
        if not self.running:
            return
        super().stop()

        pyglet.clock.unschedule(self.update)

        if self._window:
            self._window.close()
            self._window = None

    @property
    def window(self) -> Window:
        if self._window is None:
            raise RuntimeError("Window not initialized")
        return self._window

    @window.setter
    def window(self, window: Window | None):
        self._window = window

    @property
    def _interrupt_update_condition(self):
        return not self.running or not self._window or self._window.has_exit
