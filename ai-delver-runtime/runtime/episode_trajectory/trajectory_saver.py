from ._get_trajectory_dir import get_trajectory_dir
from ._trajectory_metadata_manager import TrajectoryMetadataManager
from .trajectory_stats_calculator import TrajectoryStatsCalculator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class TrajectorySaver:

    def __init__(self, agent_name: str):
        self.agent_name = agent_name

        self.metadata_manager = TrajectoryMetadataManager(agent_name)
        self.trajectory_status_calculator = TrajectoryStatsCalculator(agent_name)

    async def save_trajectory_json(self, trajectory_json: str):
        """Saves a trajectory JSON, naming it with an incrementing index."""
        # The trajectory_dir property also ensures the directory exists.
        trajectory_dir = self.trajectory_dir

        trajectory_index = await (
            self.trajectory_status_calculator.get_amount_of_trajectories()
        )

        trajectory_file_path = trajectory_dir / f"trajectory_{trajectory_index}.json"

        with open(trajectory_file_path, "w") as f:
            f.write(trajectory_json)

        metadata = await self.metadata_manager.read_metadata()
        metadata["trajectory_count"] = trajectory_index + 1
        await self.metadata_manager.write_metadata(metadata)

    @property
    def trajectory_dir(self) -> "Path":
        return get_trajectory_dir(self.agent_name)
