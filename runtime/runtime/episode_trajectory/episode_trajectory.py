import json
from dataclasses import dataclass, asdict, field
from typing import List
from .trajectory_saver import TrajectorySaver
from .snapshots import (
    FrameSnapshot,
)
from .delver_action import DelverAction


@dataclass
class EpisodeTrajectory:
    """
    Stores all the data recorded during a simulation episode, supporting both
    action-based and state-based replay methods.
    """

    actions_per_second: int
    victorious: bool = False
    level_hash: str = ""  # Unique hash of the level configuration

    # For the original, action-based replay
    delver_actions: "List[DelverAction]" = field(default_factory=list)

    # For the new, 100% accurate state-based replay
    frame_snapshots: List[FrameSnapshot] = field(default_factory=list)

    def add_delver_action(self, action: "DelverAction"):
        """Adds a delver action to the trajectory (for action-based replay)."""
        self.delver_actions.append(action)

    def add_frame_snapshot(self, frame_snapshot: "FrameSnapshot"):
        """
        Creates and adds a snapshot of the current state of all provided entities.
        """
        self.frame_snapshots.append(frame_snapshot)

    def to_json(self) -> str:
        """Converts the episode trajectory to a JSON string."""
        return json.dumps(asdict(self), indent=2)

    async def save(self, agent_name: str):
        """Saves the current trajectory to the trajectory directory."""
        await TrajectorySaver(agent_name).save_trajectory_json(self.to_json())


class EpisodeTrajectoryFactory:
    @staticmethod
    def from_json(json_string: str) -> "EpisodeTrajectory":
        """Creates an EpisodeTrajectory from a JSON string."""
        data = json.loads(json_string)

        episode_trajectory = EpisodeTrajectory(
            data["actions_per_second"], data["victorious"], data["level_hash"]
        )

        if "delver_actions" in data:
            for action_data in data["delver_actions"]:
                episode_trajectory.add_delver_action(DelverAction(**action_data))

        if "frame_snapshots" in data:
            for frame_snapshot_data in data["frame_snapshots"]:
                frame_snapshot = FrameSnapshot()

                for entity_data in frame_snapshot_data["entities"]:
                    frame_snapshot.add_entity_from_json(entity_data)

                episode_trajectory.add_frame_snapshot(frame_snapshot)

        return episode_trajectory
