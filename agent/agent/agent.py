from pathlib import Path
from .config import AGENT_SAVE_FOLDER_PATH
from runtime.episode_trajectory import TrajectoryLoader
import dill


class Agent:
    def __init__(self, name: str):
        self.name = name

        self.trajectory_loader = TrajectoryLoader(name)

    @property
    def same_name_saved(self):
        return self.save_file_path.parent.is_dir() if self.save_file_path else None

    def save(self):
        if not self.save_file_path:
            raise ValueError("Save file path is not set for the agent.")

        self.save_file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.save_file_path, "wb") as file:
            dill.dump(self, file)

    def __getstate__(self):
        """
        Custom serialization method to explicitly define the object's state.
        This prevents pickling transient or environment-specific attributes
        like Path objects, selectors, or togglers.
        We only serialize the data that is essential to the level's definition.
        """
        return {
            "name": self.name,
        }

    def __setstate__(self, state):
        """
        Custom deserialization method to reconstruct the object from its state
        and then re-initialize the transient attributes that were not serialized.
        """
        self.__dict__.update(state)

        self.trajectory_loader = TrajectoryLoader(self.name)

    @property
    def save_file_path(self):
        """
        Dynamically generates the save file path.
        This property is not serialized, thus avoiding the ModuleNotFoundError.
        """
        return (
            Path(AGENT_SAVE_FOLDER_PATH) / Path(self.name) / f"agent.dill"
            if AGENT_SAVE_FOLDER_PATH
            else None
        )
