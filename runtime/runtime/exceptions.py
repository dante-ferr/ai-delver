class SimulationError(Exception):
    """Base exception for physics and runtime simulation errors."""
    pass


class EntityNotFoundError(SimulationError):
    """Raised when trying to interact with an entity that does not exist in the simulation."""

    def __init__(self, entity_id: str):
        super().__init__(f"Entity '{entity_id}' not found in simulation space.")
        self.entity_id = entity_id
