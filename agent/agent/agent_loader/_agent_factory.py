from ..agent import Agent
from ..config import SESSION_STORAGE_KEY


class AgentFactory:
    def create_agent(self):
        """Create the default in-memory agent bound to the session workspace."""
        return Agent("Brave Delver", storage_key=SESSION_STORAGE_KEY)
