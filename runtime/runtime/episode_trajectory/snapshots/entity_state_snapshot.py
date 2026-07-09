from dataclasses import dataclass, field
from typing import List, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from runtime.world_objects.entities.entity import Entity, EntityState


@dataclass
class EntityStateSnapshot:
    """
    Captures the complete state of a single entity at a moment in time.
    This is designed to be easily serialized to JSON.
    """

    entity_id: str
    state: "EntityState"

    position: List[float]
    angle: float

    velocity: List[float] = field(default_factory=list)
    angular_velocity: float = field(default=0.0)

    entity_type: str = field(default="Entity")

    def apply_to_entity(self, entity: "Entity"):
        entity.position = (self.position[0], self.position[1])
        entity.angle = self.angle
        entity.state = self.state


class EntityStateSnapshotFactory:
    def _get_state_snapshot_args(self, entity: "Entity") -> dict[str, Any]:
        return {
            "entity_id": entity.spawn_based_id,
            "position": [entity.position[0], entity.position[1]],
            "velocity": [entity.body.velocity.x, entity.body.velocity.y],
            "angle": entity.angle,
            "angular_velocity": entity.body.angular_velocity,
            "state": entity.state.name,
        }

    def create_state_snapshot_from_entity(
        self, entity: "Entity"
    ) -> EntityStateSnapshot:
        return EntityStateSnapshot(**self._get_state_snapshot_args(entity))

    def create_state_snapshot_from_json(
        self, json: dict[str, Any]
    ) -> EntityStateSnapshot:
        return EntityStateSnapshot(**json)
