from dataclasses import dataclass, field
from typing import List, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from runtime.world_objects.world_object import WorldObject


@dataclass
class EntityStateSnapshot:
    """
    Captures the complete state of a single entity at a moment in time.
    This is designed to be easily serialized to JSON.
    """

    entity_id: str
    position: List[float]
    angle: float

    state: str = field(default="NORMAL")
    velocity: List[float] = field(default_factory=list)
    angular_velocity: float = field(default=0.0)

    entity_type: str = field(default="Entity")

    def apply_to_entity(self, entity: "WorldObject"):
        entity.position = (self.position[0], self.position[1])
        if hasattr(entity, "angle"):
            entity.angle = self.angle


class EntityStateSnapshotFactory:
    def _get_state_snapshot_args(self, entity: "WorldObject") -> dict[str, Any]:
        vx, vy = entity.velocity if hasattr(entity, "velocity") else (0.0, 0.0)
        angle = entity.angle if hasattr(entity, "angle") else 0.0
        return {
            "entity_id": entity.spawn_based_id,
            "position": [entity.position[0], entity.position[1]],
            "velocity": [vx, vy],
            "angle": angle,
            "angular_velocity": 0.0,
            "state": "NORMAL",
        }

    def create_state_snapshot_from_entity(
        self, entity: "WorldObject"
    ) -> EntityStateSnapshot:
        return EntityStateSnapshot(**self._get_state_snapshot_args(entity))

    def create_state_snapshot_from_json(
        self, json: dict[str, Any]
    ) -> EntityStateSnapshot:
        return EntityStateSnapshot(**json)
