from dataclasses import dataclass, field
from .entity_state_snapshot import (
    EntityStateSnapshot,
    EntityStateSnapshotFactory,
)
from runtime.world_objects.entities.skeletal_entity import (
    SkeletalEntity,
    LocomotionState,
)
from typing import cast, TYPE_CHECKING, Any


if TYPE_CHECKING:
    from runtime.world_objects.entities.entity import Entity


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

    def apply_to_entity(self, entity: "Entity"):
        super().apply_to_entity(entity)

        entity = cast("SkeletalEntity", entity)
        entity.locomotion_state = entity.resolve_locomotion_state(self.locomotion_state)
        entity.move_angle = self.move_angle

        if entity.is_moving_intentionally:
            entity.apply_move_visuals()

class SkeletalEntityStateSnapshotFactory(EntityStateSnapshotFactory):
    def _get_state_snapshot_args(self, entity: "Entity"):
        entity = cast("SkeletalEntity", entity)

        locomotion_state = entity.locomotion_state

        return {
            **super()._get_state_snapshot_args(entity),
            "locomotion_state": getattr(locomotion_state, "value", locomotion_state),
            "move_angle": entity.move_angle,
            "is_moving_intentionally": entity.is_moving_intentionally,
        }

    def create_state_snapshot_from_entity(
        self, entity: "Entity"
    ) -> SkeletalEntityStateSnapshot:
        entity = cast("SkeletalEntity", entity)

        return SkeletalEntityStateSnapshot(**self._get_state_snapshot_args(entity))

    def create_state_snapshot_from_json(
        self, json: dict[str, Any]
    ) -> SkeletalEntityStateSnapshot:
        return SkeletalEntityStateSnapshot(**json)
