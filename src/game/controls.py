from pyglet import window
from typing import TYPE_CHECKING
import math
from pymunk import Vec2d
from src.utils import vector_to_angle

if TYPE_CHECKING:
    from .entities.player.player import Player


class Controls:
    keys: window.key.KeyStateHandler

    def __init__(self, keys: window.key.KeyStateHandler):
        self.keys = keys

    def append_player(self, player: "Player"):
        self.player = player

    def append_camera(self, camera):
        self.camera = camera

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        self._handle_zoom(scroll_y)

    def _update_player_controls(self, dt):
        run_vector = [0, 0]

        if self.keys[window.key.RIGHT]:
            run_vector[0] += 1
        if self.keys[window.key.LEFT]:
            run_vector[0] -= 1
        if self.keys[window.key.UP]:
            run_vector[1] += 1
        if self.keys[window.key.DOWN]:
            run_vector[1] -= 1

        if run_vector == [0, 0]:
            self.player.stand()
        else:
            self.player.move(dt, vector_to_angle(run_vector))

    def _handle_zoom(self, scroll_y):
        if not self.camera:
            raise ValueError("Camera not set")
        zoom_speed = 0.1
        self.camera.zoom = self.camera.zoom + scroll_y * zoom_speed

    def update(self, dt):
        self._update_player_controls(dt)
