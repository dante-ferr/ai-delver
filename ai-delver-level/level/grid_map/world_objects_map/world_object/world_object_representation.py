from pytiling import GridElement
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytiling import GridLayer


class WorldObjectRepresentation(GridElement):
    """A representation of a world object (parent of game entities). Its name should be the same as the canvas object that represents it."""

    def __init__(
        self, position: tuple[int, int], name: str, tags: list[str] = [], **args
    ):
        super().__init__(position, name, **args)
        self.tags = tags

    def to_dict(self):
        """Serialize the world object representation to a dictionary."""
        return {
            "__class__": "WorldObjectRepresentation",
            "position": self.position,
            "name": self.name,
            "locked": self.locked,
            "unique": self.unique,
            "tags": sorted(self.tags),
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Deserialize a world object representation from a dictionary."""
        instance = cls(
            position=tuple(data["position"]),
            name=data["name"],
            tags=data.get("tags", []),
        )
        instance.locked = data.get("locked", False)
        instance.unique = data.get("unique", False)
        return instance

    @property
    def layer(self):
        return super().layer

    @layer.setter
    def layer(self, layer: "GridLayer"):
        self._layer = layer

    def add_tag(self, tag: str):
        self.tags.append(tag)

    @property
    def canvas_object_name(self):
        variation_tag = next(
            (tag for tag in self.tags if tag.startswith("variation_")), None
        )
        if not variation_tag:
            return self.name
        return variation_tag.replace("variation_", "")
