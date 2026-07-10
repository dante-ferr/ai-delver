import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .item import Item
from runtime.config import ASSETS_PATH

if TYPE_CHECKING:
    from runtime.runtime import Runtime


class Goal(Item):
    """
    The level exit.

    Position is authoritative in the Rust engine; the sprite follows it.
    """

    def __init__(self, runtime: "Runtime", variation: str, render: bool):
        self._physics_engine = runtime.physics_engine
        self._base_goal = self._physics_engine.get_goal()
        sprite_path = _resolve_goal_sprite_path(variation) if render else None
        super().__init__(
            runtime,
            sprite_path=sprite_path,
            render=render,
        )
        self._spawn_based_id = "goal"

    @property
    def position(self) -> tuple[float, float]:
        return (self._base_goal.x, self._base_goal.y)

    @position.setter
    def position(self, value: tuple[float, float]):
        pass

    def update(self, dt: float):
        self._base_goal = self._physics_engine.get_goal()
        super().update(dt)
        if self.sprite:
            x, y = self.position
            self.sprite.update(x=x, y=y)


GOAL_SPRITES_DIR = ASSETS_PATH / "img/representations/goal"
GOAL_VARIATION_ALIASES = {"default": "uranium_cake"}


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
