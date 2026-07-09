from ._trajectory_metadata_manager import TrajectoryMetadataManager
from ._get_trajectory_dir import get_trajectory_dir
import json
import logging
from typing import TYPE_CHECKING, Optional, List, Dict, Any
import asyncio
import aiofiles

if TYPE_CHECKING:
    from pathlib import Path
    from .episode_trajectory import EpisodeTrajectory


class TrajectoryStatsCalculator:
    def __init__(self, agent_name: str):
        self.agent_name = agent_name

        self.metadata_manager = TrajectoryMetadataManager(agent_name)

    async def get_stats(self) -> Dict[str, int]:
        """
        Calculates trajectory statistics, incrementally updating from the last run.
        Stats are read from and saved to the metadata file to avoid re-reading all files.
        """
        metadata = await self.metadata_manager.read_metadata()
        stats = metadata.get("stats", {"amount": 0, "victories": 0})
        last_processed_count = stats.get("amount", 0)
        total_trajectories = metadata.get("trajectory_count", 0)

        if last_processed_count >= total_trajectories:
            return stats

        logging.info(
            f"New trajectories detected. Updating stats from index {last_processed_count}."
        )

        tasks = self._get_new_trajectory_tasks(last_processed_count, total_trajectories)

        if not tasks:
            await self._update_and_save_stats(stats, total_trajectories, metadata)
            return stats

        await self._process_trajectory_tasks(tasks, stats)
        await self._update_and_save_stats(stats, total_trajectories, metadata)

        return stats

    async def get_stats_legacy(self) -> Dict[str, int]:
        """
        Calculates trajectory statistics by reading all trajectory files every time.
        This is a "legacy" method for testing and validation purposes.
        """
        stats = {"amount": 0, "victories": 0}
        trajectory_files = await asyncio.to_thread(
            list, self.trajectory_dir.glob("trajectory_*.json")
        )

        tasks = [
            asyncio.create_task(self._read_and_parse_trajectory(path))
            for path in trajectory_files
        ]

        if not tasks:
            return stats

        stats["amount"] = len(tasks)
        await self._process_trajectory_tasks(tasks, stats)
        return stats

    def _get_new_trajectory_tasks(
        self, start_index: int, end_index: int
    ) -> List[asyncio.Task]:
        """Creates asyncio tasks for reading new trajectory files."""
        tasks = []
        for i in range(start_index, end_index):
            path = self.trajectory_dir / f"trajectory_{i}.json"
            if not path.is_file():
                logging.warning(f"Expected trajectory file not found: {path}")
                continue
            tasks.append(asyncio.create_task(self._read_and_parse_trajectory(path)))
        return tasks

    @staticmethod
    async def _process_trajectory_tasks(
        tasks: List[asyncio.Task], stats: Dict[str, int]
    ):
        """Processes completed trajectory tasks and updates the victory count."""
        for future in asyncio.as_completed(tasks):
            trajectory = await future
            if trajectory and trajectory.victorious:
                stats["victories"] += 1

    async def _update_and_save_stats(
        self, stats: Dict[str, int], total_trajectories: int, metadata: Dict[str, Any]
    ):
        """Updates the stats dictionary and writes it back to the metadata file."""
        stats["amount"] = total_trajectories
        metadata["stats"] = stats
        await self.metadata_manager.write_metadata(metadata)

    @staticmethod
    async def _read_and_parse_trajectory(
        file_path: "Path",
    ) -> Optional["EpisodeTrajectory"]:
        """Asynchronously reads and parses a single trajectory JSON file."""
        from .episode_trajectory import EpisodeTrajectoryFactory

        try:
            async with aiofiles.open(file_path, mode="r") as f:
                content = await f.read()
                # json.loads is sync, but for small files, it's fine here.
                # For very large files, consider running in an executor.
                return EpisodeTrajectoryFactory.from_json(content)
        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"Could not read or parse trajectory {file_path}: {e}")
            return None

    async def get_amount_of_trajectories(self) -> int:
        """Gets the total number of trajectories from the metadata."""
        metadata = await self.metadata_manager.read_metadata()
        amount = metadata.get("trajectory_count", 0)
        return amount

    @property
    def trajectory_dir(self) -> "Path":
        """Returns the path to the agent's trajectory directory."""
        return get_trajectory_dir(self.agent_name)
