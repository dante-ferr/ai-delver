from .. import ViewableRuntime
from .game_controls import GameControls


class Game(ViewableRuntime):
    def _create_controls(self):
        self.controls = GameControls(self.keys)
        self.controls.append_delver(self.delver)

    def update(self, dt):
        dt *= self.execution_speed
        super().update(dt)

        # def _check_collisions(self):

    #     if self.delver.check_collision(self.goal):
    #         from app_manager import app_manager

    #         app_manager.stop_game()
