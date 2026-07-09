from app.components import SaveButton
from loaders import agent_loader
from agent.config import AGENT_SAVE_FOLDER_PATH


class AgentSaveButton(SaveButton):

    def __init__(self, master):
        super().__init__(master, AGENT_SAVE_FOLDER_PATH, "agent")

    def _save(self):
        super()._save()
        agent_loader.agent.save()

    @property
    def file_name(self) -> str:
        return agent_loader.agent.name
