import logging
from runtime.episode_trajectory.episode_trajectory import (
    EpisodeTrajectory,
    EpisodeTrajectoryFactory,
)
from ._get_trajectory_dir import get_trajectory_dir
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class TrajectoryLoader:
    """
    A class for loading and saving episode trajectories.
    """

    def __init__(self, agent_name: str):
        self.agent_name = agent_name

        self._trajectory: None | EpisodeTrajectory = None

    @property
    def trajectory(self):
        return self._trajectory

    @trajectory.setter
    def trajectory(self, new_trajectory):
        self._trajectory = new_trajectory

    def load_trajectory(
        self,
        index: int,
    ):
        """
        Loads a trajectory by its index from the current level's directory
        and returns its JSON content as a string.
        """
        try:
            # The trajectory_dir property also ensures the directory exists.
            trajectory_dir = self.trajectory_dir
        except ValueError as e:
            logging.error(f"Cannot load trajectory: {e}")
            return None

        trajectory_file_path = trajectory_dir / f"trajectory_{index}.json"

        if not trajectory_file_path.is_file():
            logging.warning(f"Trajectory file not found: {trajectory_file_path}")
            return None

        try:
            with open(trajectory_file_path, "r") as f:
                trajectory_json = f.read()
                trajectory = EpisodeTrajectoryFactory.from_json(trajectory_json)
                self.trajectory = trajectory
                return trajectory

        except IOError as e:
            logging.error(f"Error reading trajectory file {trajectory_file_path}: {e}")
            return None

    @property
    def trajectory_dir(self) -> "Path":
        return get_trajectory_dir(self.agent_name)
