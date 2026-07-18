from pytiling import GridElement
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytiling import GridLayer


class WorldObjectRepresentation(GridElement):
    """A representation of a world object (parent of game entities). Its name should be the same as the canvas object that represents it."""

    def __init__(
        self,
        position: tuple[int, int],
        name: str,
        tags: list[str] | None = None,
        size: tuple[int, int] = (1, 1),
        **args,
    ):
        super().__init__(position, name, size=size, **args)
        self.tags = list(tags) if tags is not None else []

    def to_dict(self):
        """Serialize the world object representation to a dictionary."""
        return {
            "__class__": "WorldObjectRepresentation",
            "position": self.position,
            "name": self.name,
            "locked": self.locked,
            "unique": self.unique,
            "size": list(self.size),
            "tags": sorted(self.tags),
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Deserialize a world object representation from a dictionary."""
        raw_size = data.get("size", (1, 1))
        instance = cls(
            position=tuple(data["position"]),
            name=data["name"],
            tags=data.get("tags", []),
            size=(int(raw_size[0]), int(raw_size[1])),
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
