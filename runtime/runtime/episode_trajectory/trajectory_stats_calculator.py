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

    async def get_stats(self) -> Dict[str, Any]:
        """
        Calculates trajectory statistics, incrementally updating from the last run.
        Stats are read from and saved to the metadata file to avoid re-reading all files.
        """
        metadata = await self.metadata_manager.read_metadata()
        stats = metadata.get("stats", {
            "amount": 0,
            "victories": 0,
            "victories_history": [],
            "steps_history": []
        })

        if "victories_history" not in stats:
            stats["victories_history"] = []
        if "steps_history" not in stats:
            stats["steps_history"] = []

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

    async def get_stats_legacy(self) -> Dict[str, Any]:
        """
        Calculates trajectory statistics by reading all trajectory files every time.
        This is a "legacy" method for testing and validation purposes.
        """
        stats = {
            "amount": 0,
            "victories": 0,
            "victories_history": [],
            "steps_history": []
        }
        trajectory_files = await asyncio.to_thread(
            list, self.trajectory_dir.glob("trajectory_*.json")
        )

        def get_index_from_path(p):
            try:
                return int(p.stem.split("_")[1])
            except Exception:
                return 999999
        trajectory_files.sort(key=get_index_from_path)

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
        tasks: List[asyncio.Task], stats: Dict[str, Any]
    ):
        """Processes completed trajectory tasks and updates the victory count and histories."""
        results = await asyncio.gather(*tasks)

        if "victories_history" not in stats:
            stats["victories_history"] = []
        if "steps_history" not in stats:
            stats["steps_history"] = []

        current_accum_victories = stats.get("victories", 0)

        for trajectory in results:
            if trajectory is None:
                stats["steps_history"].append(0)
                stats["victories_history"].append(current_accum_victories)
                continue

            is_victory = trajectory.victorious
            if is_victory:
                current_accum_victories += 1

            stats["victories_history"].append(current_accum_victories)

            steps = len(trajectory.frame_snapshots) if trajectory.frame_snapshots else len(trajectory.delver_actions)
            stats["steps_history"].append(steps)

        stats["victories"] = current_accum_victories

    async def _update_and_save_stats(
        self, stats: Dict[str, Any], total_trajectories: int, metadata: Dict[str, Any]
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
