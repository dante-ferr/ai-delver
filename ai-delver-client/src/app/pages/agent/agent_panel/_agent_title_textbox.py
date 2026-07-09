from app.components import TitleTextbox
from loaders import agent_loader


class AgentTitleTextbox(TitleTextbox):

    def __init__(self, master):
        super().__init__(master, agent_loader.agent.name)

    def _update_name(self, event=None):
        agent_loader.agent.name = self._get_input()
