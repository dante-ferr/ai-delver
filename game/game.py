import json
import pyglet
from game.controls import Controls
import pymunk
from typing import Any
from .entities.player import Player

with open("game/config.json", "r") as file:
    config_data = json.load(file)

window_width = config_data["window_width"]
window_height = config_data["window_height"]


class Game:
    entities: list[Any] = []

    def __init__(self):
        self.window = pyglet.window.Window()
        self.window.set_size(window_width, window_height)

        self.space = pymunk.Space()
        self.space.gravity = (0, 0)

        # Initialize player
        player = Player(self.space)
        self.entities.append(player)
        self.player = player

        # player.set_position(
        #     window_width / 2, window_height / 2
        # )
        player.set_scale(2, 2)
        player.set_angle(180)

        # Register the key press event
        self.keys = pyglet.window.key.KeyStateHandler()
        self.window.push_handlers(self.keys)

    def update(self, dt):
        self.window.clear()
        controls = Controls(self.keys, self.player)
        controls.update(dt)
        self.player.update(dt)

    def run(self):
        pyglet.clock.schedule_interval(
            self.update, 1 / float(config_data["fps"])
        )  # Update at 60 FPS
        pyglet.app.run()
