from loaders import level_loader
from app.components import TitleTextbox


class LevelTitleTextbox(TitleTextbox):

    def __init__(self, master):
        super().__init__(master, level_loader.level.name)
        self.set_dirty(level_loader.dirty)
        level_loader.add_dirty_listener(self.set_dirty)

    def _update_name(self, event=None):
        super()._update_name(event)
        new_name = self._get_input()
        if new_name != level_loader.level.name:
            level_loader.level.name = new_name
            level_loader.mark_dirty()
