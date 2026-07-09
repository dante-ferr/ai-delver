from ..viewable_runtime import ViewableRuntime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from runtime.episode_trajectory import EpisodeTrajectory
    from level import Level


class Replay(ViewableRuntime):
    """
    An abstract base class for all replay types.
    It handles the common logic of time accumulation and trajectory management.
    """

    def __init__(
        self,
        level: "Level",
        trajectory: "EpisodeTrajectory",
        physics: bool,
    ):
        super().__init__(level, physics=physics)
        self.trajectory = trajectory

        if self.actions_per_second > 0:
            self.time_per_action = 1.0 / self.actions_per_second
        else:
            self.time_per_action = float("inf")

        self.time_accumulator = 0.0
        self.current_step_index = 0

        self.is_replay = True

    @property
    def actions_per_second(self) -> int:
        return self.trajectory.actions_per_second
