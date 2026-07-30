from dataclasses import dataclass, field
from .entity_state_snapshot import (
    EntityStateSnapshot,
    EntityStateSnapshotFactory,
)
from runtime.world_objects.skeletal_entity import (
    SkeletalEntity,
)
from typing import cast, TYPE_CHECKING, Any


if TYPE_CHECKING:
    from runtime.world_objects.world_object import WorldObject


@dataclass
class SkeletalEntityStateSnapshot(EntityStateSnapshot):
    """
    Captures the complete state of a single skeletal entity at a moment in time.
    This is designed to be easily serialized to JSON.
    """

    locomotion_state: str = field(default="IDLE")
    move_angle: float | None = field(default=None)
    is_moving_intentionally: bool = field(default=False)

    entity_type: str = field(default="SkeletalEntity")

    def apply_to_entity(self, entity: "WorldObject"):
        super().apply_to_entity(entity)

        entity = cast("SkeletalEntity", entity)
        entity.is_moving_intentionally = self.is_moving_intentionally
        entity.is_moving = self.is_moving_intentionally

        locomotion = self._corrected_locomotion_state()
        locomotion = self._apply_replay_landing(entity, locomotion)
        entity.locomotion_state = entity.resolve_locomotion_state(locomotion)
        entity.move_angle = self.move_angle

        if entity.is_moving_intentionally:
            entity.apply_move_visuals()

        self._remember_replay_airborne_vy(entity, locomotion)

    def _corrected_locomotion_state(self) -> str:
        """
        Fix airborne labels that disagree with vertical velocity.

        Older showcase trajectories inverted rising/falling (FALL while ascending,
        JUMP while descending). Trust vy so replays show fall on descent even for
        those recordings, without rewriting already-correct GO_UP/FALL labels.
        """
        locomotion = self.locomotion_state
        if locomotion not in ("JUMP", "FALL", "GO_UP"):
            return locomotion
        if not self.velocity or len(self.velocity) < 2:
            return locomotion
        vy = float(self.velocity[1])
        if abs(vy) <= 1.0:
            return locomotion
        if vy > 0.0 and locomotion == "FALL":
            return "JUMP"
        if vy <= 0.0 and locomotion in ("JUMP", "GO_UP"):
            return "FALL"
        return locomotion

    def _apply_replay_landing(self, entity: "SkeletalEntity", locomotion: str) -> str:
        """
        Insert/hold LAND on hard landings.

        Showcase trajectories historically jumped straight to IDLE/RUN on contact, and
        even with a single LAND frame the next snapshot would cancel the clip. Match
        live play: LAND on fast fall contact, then keep it until the anim finishes.
        """
        airborne = ("JUMP", "FALL", "GO_UP")
        threshold = SkeletalEntity.LAND_ANIMATION_REQUIRED_FALLING_SPEED

        current = getattr(entity.locomotion_state, "value", entity.locomotion_state)
        current_name = current if isinstance(current, str) else str(current)

        if (
            locomotion in ("IDLE", "RUN")
            and current_name in airborne
            and entity.previous_on_air_vy <= threshold
        ):
            entity.previous_on_air_vy = 0.0
            return "LAND"

        if locomotion == "LAND":
            entity.previous_on_air_vy = 0.0
            return "LAND"

        # Live play waits for the land clip; don't let IDLE/RUN snapshots cut it short.
        if current_name == "LAND" and locomotion in ("IDLE", "RUN"):
            return "LAND"

        return locomotion

    def _remember_replay_airborne_vy(self, entity: "SkeletalEntity", locomotion: str):
        if locomotion not in ("JUMP", "FALL", "GO_UP"):
            return
        if not self.velocity or len(self.velocity) < 2:
            return
        vy = float(self.velocity[1])
        if abs(vy) > 1.0:
            entity.previous_on_air_vy = vy

class SkeletalEntityStateSnapshotFactory(EntityStateSnapshotFactory):
    def _get_state_snapshot_args(self, entity: "WorldObject"):
        entity = cast("SkeletalEntity", entity)

        locomotion_state = entity.locomotion_state

        return {
            **super()._get_state_snapshot_args(entity),
            "locomotion_state": getattr(locomotion_state, "value", locomotion_state),
            "move_angle": entity.move_angle,
            "is_moving_intentionally": entity.is_moving_intentionally,
        }

    def create_state_snapshot_from_entity(
        self, entity: "WorldObject"
    ) -> SkeletalEntityStateSnapshot:
        entity = cast("SkeletalEntity", entity)

        return SkeletalEntityStateSnapshot(**self._get_state_snapshot_args(entity))

    def create_state_snapshot_from_json(
        self, json: dict[str, Any]
    ) -> SkeletalEntityStateSnapshot:
        return SkeletalEntityStateSnapshot(**json)
