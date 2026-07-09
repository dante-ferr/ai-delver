from dataclasses import dataclass, field
from .entity_state_factory_provider import (
    EntityStateSnapshotFactoryProvider,
)
import runtime.world_objects.entities as entities
from typing import List, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .entity_state_snapshot import EntityStateSnapshot
    from runtime.world_objects.entities.entity import Entity


@dataclass
class FrameSnapshot:
    """
    Represents the state of all dynamic entities in the simulation at a single frame.
    """

    entities: "List[EntityStateSnapshot]" = field(default_factory=list)

    def add_entity_from_json(self, json: dict[str, Any]):
        snapshot_state_factory = EntityStateSnapshotFactoryProvider().from_entity_type(
            getattr(entities, json["entity_type"])
        )
        entity_state = snapshot_state_factory.create_state_snapshot_from_json(json)
        self.add_entity_snapshot(entity_state)

    def add_entity(self, entity: "Entity"):
        snapshot_state_factory = EntityStateSnapshotFactoryProvider().from_entity_type(
            type(entity)
        )
        entity_state = snapshot_state_factory.create_state_snapshot_from_entity(entity)
        self.add_entity_snapshot(entity_state)

    def add_entity_snapshot(self, entity_state_snapshot: "EntityStateSnapshot"):
        self.entities.append(entity_state_snapshot)
