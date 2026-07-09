from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from runtime.runtime import Runtime


class WorldObject:
    def __init__(self, runtime: "Runtime"):
        self.runtime = runtime

        self._position = (0.0, 0.0)
        self._spawn_based_id: str | None = None

        self._bounding_box: tuple[float, float, float, float] | None = None

    @property
    def bounding_box(self):
        return self._bounding_box

    @bounding_box.setter
    def bounding_box(self, bounding_box: tuple[float, float, float, float]):
        self._bounding_box = bounding_box

    @property
    def position(self):
        """Get the position of the world object."""
        return self._position

    @position.setter
    def position(self, position: tuple[float, float]):
        """Set the position of the world object."""
        self._conditionally_set_spawn_based_id(position)
        self._position = position

    def _conditionally_set_spawn_based_id(self, position: tuple[float, float]):
        if self._spawn_based_id is None:
            self._spawn_based_id = (
                f"{self.__class__.__name__}:{position[0]}_{position[1]}"
            )

    @property
    def spawn_based_id(self):
        if self._spawn_based_id is None:
            raise ValueError(
                "World object has no spawn_based_id. The object's position must be set first."
            )

        return self._spawn_based_id

    def update(self, dt):
        """Update the world object."""
        pass

    def draw(self, dt):
        """Draw the world object."""
        pass

    @property
    def tile_size(self):
        """Get the size of a tile in the world."""
        return self.runtime.level.map.tile_size

    def check_collision(self, other):
        """Check if this item collides with another object's bounding box."""
        if not self.bounding_box or not other.bounding_box:
            return False

        x1_min, y1_min, x1_max, y1_max = self.bounding_box
        x2_min, y2_min, x2_max, y2_max = other.bounding_box

        return not (
            x1_max < x2_min or x1_min > x2_max or y1_max < y2_min or y1_min > y2_max
        )

    def cleanup(self):
        pass

    @property
    def in_replay(self):
        return self.runtime.is_replay
