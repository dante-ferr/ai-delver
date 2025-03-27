import json
import pyglet
from game.controls import Controls
from .level_setup import tilemap_renderer_factory
from .camera import Camera, Camera
from .space import space
from pyglet_dragonbones import config as pdb_config
from .level_setup import world_objects_controller_factory

with open("src/game/config.json", "r") as file:
    config_data = json.load(file)

pdb_config.fps = config_data["fps"]


class Game:
    def __init__(self):
        display = pyglet.display.get_display()
        screen = display.get_screens()[0]

        self.window = pyglet.window.Window(fullscreen=False, resizable=False)

        self.camera: None | Camera = None

        def _callback(dt):
            self.window.maximize()
            pyglet.clock.schedule_once(self._on_screen_maximize_interval, 0.01)

        pyglet.clock.schedule_once(_callback, 0.1)

        # Initialize camera
        self.entities_controller = world_objects_controller_factory(space)
        self.delver = self.entities_controller.get_world_object_by_name("delver")

        # Initialize tilemap
        # self.tilemap_renderer = tilemap_factory()
        self.tilemap_renderer = tilemap_renderer_factory()

        # Initialize controls
        self.keys = pyglet.window.key.KeyStateHandler()
        self.controls = Controls(self.keys)
        self.controls.append_delver(self.delver)
        self.controls.append_camera(self.camera)

        self.window.push_handlers(
            self.keys,
            on_mouse_scroll=self.controls.on_mouse_scroll,
        )

    def _on_screen_maximize_interval(self, dt):
        self._lock_window_size()

        self.camera = Camera(self.window, start_zoom=0.5, min_zoom=0.25, max_zoom=2)
        self.camera.start_following(self.delver)

    def _lock_window_size(self):
        """Locks the window size completely (even on Linux)"""
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
        self.window.clear()

        self.tilemap_renderer.render_all_layers()

        self.entities_controller.update_world_objects(dt)

        self.controls.update(dt)

        if self.camera is not None:
            with self.camera:
                pass

        space.step(dt)

    def run(self):
        pyglet.clock.schedule_interval(
            self.update, 1 / float(config_data["fps"])
        )  # Update at 60 FPS
        pyglet.app.run()
