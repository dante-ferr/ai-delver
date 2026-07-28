from ._get_trajectory_dir import get_trajectory_dir
from ._trajectory_metadata_manager import TrajectoryMetadataManager
from .trajectory_stats_calculator import TrajectoryStatsCalculator
from .run_index import append_run_index_entry, extract_run_index_entry
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

KIND_TRAIN = "train"
KIND_PLAY = "play"


class TrajectorySaver:

    def __init__(self, agent_name: str):
        self.agent_name = agent_name

        self.metadata_manager = TrajectoryMetadataManager(agent_name)
        self.trajectory_status_calculator = TrajectoryStatsCalculator(agent_name)

    async def save_trajectory_json(
        self,
        trajectory_json: str,
        kind: str = KIND_TRAIN,
        cycle: int | None = None,
    ):
        """Saves a trajectory JSON, naming it with an incrementing index.

        ``kind`` is recorded in metadata ``trajectory_kinds`` so training stats
        can ignore play/evaluation trajectories while still allowing replay.

        A lightweight ``run_index`` row is appended alongside so the GUI can
        paint the run grid without opening every trajectory file.
        """
        if kind not in (KIND_TRAIN, KIND_PLAY):
            kind = KIND_TRAIN

        trajectory_dir = self.trajectory_dir

        trajectory_index = await (
            self.trajectory_status_calculator.get_amount_of_trajectories()
        )

        trajectory_file_path = trajectory_dir / f"trajectory_{trajectory_index}.json"

        with open(trajectory_file_path, "w") as f:
            f.write(trajectory_json)

        metadata = await self.metadata_manager.read_metadata()
        kinds = metadata.setdefault("trajectory_kinds", [])
        if not isinstance(kinds, list):
            kinds = []
            metadata["trajectory_kinds"] = kinds

        # Legacy trajectories without kinds are treated as train.
        while len(kinds) < trajectory_index:
            kinds.append(KIND_TRAIN)
        if len(kinds) == trajectory_index:
            kinds.append(kind)
        else:
            kinds[trajectory_index] = kind

        try:
            entry = extract_run_index_entry(
                trajectory_json, kind=kind, cycle=cycle
            )
        except Exception:
            entry = {
                "level_hash": "",
                "victorious": False,
                "kind": kind,
                "total_reward": None,
                "jump_takeoffs": None,
                "policy_confidence": None,
                "steps": None,
                "actions_per_second": None,
                "cycle": cycle,
            }
        append_run_index_entry(metadata, trajectory_index, entry)

        metadata["trajectory_count"] = trajectory_index + 1
        await self.metadata_manager.write_metadata(metadata)

    @property
    def trajectory_dir(self) -> "Path":
        return get_trajectory_dir(self.agent_name)
