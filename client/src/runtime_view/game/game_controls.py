from pyglet import window
from ..view_controls import ViewControls


class GameControls(ViewControls):
    keys: window.key.KeyStateHandler

    def __init__(self, keys: window.key.KeyStateHandler):
        super().__init__(keys)
        self._space_was_down = False

    def _update_delver_controls(self, dt):
        run_direction = 0

        if self.keys[window.key.RIGHT]:
            run_direction += 1
        if self.keys[window.key.LEFT]:
            run_direction -= 1

        space_is_down = self.keys[window.key.SPACE]
        if space_is_down and not self._space_was_down:
            self.delver.jump(dt)
        self._space_was_down = space_is_down

        if run_direction != 0:
            self.delver.run(dt, run_direction)

    def update(self, dt):
        self._update_delver_controls(dt)
