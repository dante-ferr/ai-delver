from .world_object import WorldObject
from typing import Optional, Any, TYPE_CHECKING


if TYPE_CHECKING:
    from pyglet.image.animation import Animation
    from pyglet.graphics import Batch


class Item(WorldObject):

    def __init__(
        self,
        runtime,
        sprite_path: Optional[str] = None,
        render=True,
        animation: Optional["Animation"] = None,
        batch: Optional["Batch"] = None,
        size: tuple[int, int] = (24, 24),
        base_object: Any = None,
    ):
        super().__init__(runtime, base_object=base_object)

        self.render = render
        self.size: tuple[int, int] = size

        if render:
            self.batch = batch
            self.sprite = self._create_sprite(sprite_path, animation)

            self._update_sprite_position()
        else:
            self.sprite = None

    def _create_sprite(
        self, sprite_path: Optional[str], animation: Optional["Animation"]
    ):
        from pyglet import image

        if sprite_path:
            img = image.load(sprite_path)
            return self._get_sprite(img)
        elif animation:
            return self._get_sprite(animation)

    def _get_sprite(self, img: Any):
        from pyglet import sprite

        spr = sprite.Sprite(img, batch=self.batch)
        # Sprite() may wrap a Texture that does not keep ImageData anchors —
        # set them on the sprite's image or the sprite is bottom-left anchored
        # while callers position it as if it were center-anchored.
        spr.image.anchor_x = spr.width // 2
        spr.image.anchor_y = spr.height // 2
        return spr

    def _compensate_offset_centering(self):
        self.position = (
            self.position[0] + self.tile_size[0] / 2,
            self.position[1] + self.tile_size[1] / 2,
        )

    @property
    def position(self):
        return super().position

    @position.setter
    def position(self, position: tuple[float, float]):
        self._position = position
        self._conditionally_set_spawn_based_id(position)
        if self.sprite:
            self._update_sprite_position()

    def _update_sprite_position(self):
        if self.sprite:
            self.sprite.update(x=self.position[0], y=self.position[1])

    def update(self, dt):
        """Update the item and its sprite if needed."""
        x, y = self.position
        width, height = self.size
        self.bounding_box = (
            x - width // 2,
            y - height // 2,
            x + width // 2,
            y + height // 2,
        )

    def draw(self, dt):
        """Draw the sprite if it exists."""
        if self.sprite:
            self.sprite.draw()

    def delete(self):
        """Clean up the sprite when no longer needed."""
        if self.sprite:
            self.sprite.delete()
