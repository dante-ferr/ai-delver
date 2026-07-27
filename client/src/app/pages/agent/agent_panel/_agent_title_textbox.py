from app.components import TitleTextbox
from loaders import agent_loader
from state_managers import training_state_manager


class AgentTitleTextbox(TitleTextbox):

    def __init__(self, master):
        super().__init__(master, agent_loader.agent.name)
        training_state_manager.add_disable_on_train_element(self)
        self.set_dirty(agent_loader.dirty)
        agent_loader.add_dirty_listener(self.set_dirty)

    def _update_name(self, event=None):
        new_name = self._get_input().strip()
        if not new_name:
            return
        if new_name != agent_loader.agent.name:
            agent_loader.agent.name = new_name
            agent_loader.mark_dirty()
            # Persist display name into session meta without binding.
            if hasattr(agent_loader, "_write_session_meta"):
                agent_loader._write_session_meta()
        self._refresh_navbar_title()

    @staticmethod
    def _refresh_navbar_title():
        from app_manager import app_manager

        editor = getattr(app_manager, "_editor", None)
        if editor is not None:
            editor.navbar.refresh_document_title()
