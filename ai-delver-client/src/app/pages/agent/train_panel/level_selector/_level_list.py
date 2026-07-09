from app.components import SortableList
from typing import Callable


class LevelList(SortableList):
    def __init__(self, master, on_amount_of_episodes_change: Callable, **kwargs):
        from state_managers import training_state_manager

        super().__init__(master, remove_box_button=True, **kwargs)

        self.on_amount_of_episodes_change = on_amount_of_episodes_change

        training_state_manager.training_level_list_component = self

    def add_box(self, name: str, **kwargs):
        super().add_box(name, **kwargs)

        self.on_amount_of_episodes_change()
