import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .item import Item
from runtime.config import ASSETS_PATH

if TYPE_CHECKING:
    from runtime.runtime import Runtime
    from level.grid_map.world_objects_map.world_object import WorldObjectRepresentation


class Goal(Item):
    """
    The level exit.

    Drawn like tile sprites: bottom-left of the footprint in pytiling world space
    (Y-up, one tile above physics cell bottoms), with a bottom-left image anchor.
    """

    def __init__(
        self,
        runtime: "Runtime",
        variation: str | None = None,
        render: bool = True,
    ):
        self._physics_engine = runtime.physics_engine
        base_object = self._physics_engine.get_goal()
        resolved = (
            variation
            if variation is not None
            else _variation_from_level(runtime.level)
        )
        sprite_path = _resolve_goal_sprite_path(resolved) if render else None
        super().__init__(
            runtime,
            sprite_path=sprite_path,
            render=render,
            base_object=base_object,
        )
        self._spawn_based_id = "goal"
        self._align_sprite_to_footprint()
        if self.sprite:
            x, y = self.position
            self.sprite.update(x=x, y=y)

    def _goal_element(self) -> "WorldObjectRepresentation | None":
        essentials = self.runtime.level.map.world_objects_map.get_layer("essentials")
        for element in essentials.elements:
            if element.name == "goal":
                return element
        return None

    def _footprint_size(self) -> tuple[int, int]:
        from level.world_object_sizes import world_object_size

        element = self._goal_element()
        if element is None:
            return world_object_size("goal")
        size = (int(element.size[0]), int(element.size[1]))
        if size == (1, 1):
            return world_object_size("goal")
        return size

    def _align_sprite_to_footprint(self) -> None:
        """Scale sprite to the footprint and use a bottom-left anchor (tile convention)."""
        if not self.sprite:
            return
        tile_w, tile_h = self.runtime.level.map.tile_size
        size_w, size_h = self._footprint_size()
        target_w = max(1, size_w * tile_w)
        target_h = max(1, size_h * tile_h)
        self.sprite.image.anchor_x = 0
        self.sprite.image.anchor_y = 0
        self.sprite.scale_x = target_w / max(1, self.sprite.width)
        self.sprite.scale_y = target_h / max(1, self.sprite.height)
        self.size = (target_w, target_h)

    @property
    def position(self) -> tuple[float, float]:
        """Bottom-left of the footprint in tile-sprite world coordinates."""
        element = self._goal_element()
        tile_w, tile_h = self.runtime.level.map.tile_size
        grid_h = self.runtime.level.map.grid_size[1]
        if element is None:
            # Fallback: physics center → footprint BL in tile space.
            size_w, size_h = self._footprint_size()
            return (
                self.base_object.x - size_w * tile_w / 2,
                self.base_object.y - size_h * tile_h / 2 + tile_h,
            )
        bx, by = element.position
        # Same convention as LayerRenderer / grid_pos_to_actual_pos for cell (bx, by).
        return (bx * tile_w, (grid_h - by) * tile_h)

    @position.setter
    def position(self, value: tuple[float, float]):
        pass

    def update(self, dt: float):
        self.base_object = self._physics_engine.get_goal()
        x, y = self.position
        width, height = self.size
        # Bottom-left anchored (same as tile sprites), not center like Item.
        self.bounding_box = (x, y, x + width, y + height)
        if self.sprite:
            self.sprite.update(x=x, y=y)


GOAL_SPRITES_DIR = ASSETS_PATH / "img/nxt/goal"
GOAL_VARIATION_ALIASES = {"default": "uranium_cake", "goal": "uranium_cake"}


def _variation_from_level(level) -> str:
    """Read the editor-placed goal variation from its ``variation_*`` tag."""
    essentials = level.map.world_objects_map.get_layer("essentials")
    for element in essentials.elements:
        if element.name == "goal":
            return element.canvas_object_name
    return "default"


def _resolve_goal_sprite_path(variation: str) -> str:
    effective_variation = GOAL_VARIATION_ALIASES.get(variation, variation)
    candidate_path = GOAL_SPRITES_DIR / f"{effective_variation}.png"
    if candidate_path.exists():
        return str(candidate_path)

    available_sprites = sorted(
        p for p in GOAL_SPRITES_DIR.glob("*.png") if p.is_file()
    )
    if not available_sprites:
        raise FileNotFoundError(
            f"No goal sprite assets found in {GOAL_SPRITES_DIR}."
        )

    fallback_path: Path = available_sprites[0]
    logging.warning(
        "Goal sprite variation '%s' not found. Falling back to '%s'.",
        variation,
        fallback_path.stem,
    )
    return str(fallback_path)
