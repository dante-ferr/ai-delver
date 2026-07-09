import dill
from ._agent_factory import AgentFactory
from pathlib import Path
import logging
from ..agent import Agent
from typing import cast


class AgentLoader:

    def __init__(self):
        self.factory = AgentFactory()
        self._create_new_agent()

    def load_agent(self, path: str | Path):
        """Loads a agent from a file. The path of the agent directory must be provided (instead of the agent file itself)."""
        if type(path) == str:
            path = Path(path)
        path = cast(Path, path)
        file_path = path / "agent.dill"

        if file_path.is_file():
            with open(file_path, "rb") as file:
                logging.info("Loading existing agent")
                self._agent = dill.load(file)
        else:
            logging.info("Creating new agent")
            self._create_new_agent()

        return self.agent

    @property
    def agent(self):
        if self._agent is None:
            raise ValueError("The agent doesn't exist.")
        return self._agent

    def _create_new_agent(self):
        self._agent: "Agent" = self.factory.create_agent()
