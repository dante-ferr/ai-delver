from runtime.world_objects.entities.skeletal_entity import SkeletalEntity
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import EntityStateSnapshotFactory


class EntityStateSnapshotFactoryProvider:
    def from_entity_type(self, entity_type: type) -> "EntityStateSnapshotFactory":
        from . import (
            EntityStateSnapshotFactory,
            SkeletalEntityStateSnapshotFactory,
        )

        if self._check_relationship(entity_type, SkeletalEntity):
            return SkeletalEntityStateSnapshotFactory()
        else:
            return EntityStateSnapshotFactory()

    def _check_relationship(self, type_1, type_2):
        return issubclass(type_1, type_2) or type_1 == type_2
