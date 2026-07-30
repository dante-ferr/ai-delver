"""Export editor representation PNGs from DragonBones entities."""

from __future__ import annotations

from pathlib import Path

from src.config import config

from ._import_exporters import ensure_dragonbones_on_path

_DEFAULT_ANIMATION = "idle"
_DEFAULT_FRAME = 0


def representation_settings(entity_name: str) -> tuple[str, int]:
    """
    Read per-entity representation animation/frame from config.

    Falls back to idle / 0 when the entity table or a key is missing.
    """
    animation = _DEFAULT_ANIMATION
    frame = _DEFAULT_FRAME
    try:
        entities = config.DRAGONBONES
        entity_cfg = getattr(entities, entity_name)
    except AttributeError:
        return animation, frame

    try:
        animation = str(entity_cfg.REPRESENTATION_ANIMATION)
    except AttributeError:
        pass
    try:
        frame = int(entity_cfg.REPRESENTATION_FRAME)
    except AttributeError:
        pass
    return animation, frame


def export_entity_representation(skeleton_path: Path) -> Path:
    """Export ``assets/img/representations/{name}.png`` for one DragonBones entity."""
    ensure_dragonbones_on_path()
    from pyglet_dragonbones.utils.export_animation_frame import export_animation_frame

    entity_name = skeleton_path.name
    animation, frame = representation_settings(entity_name)
    output_path = config.ASSETS_PATH / "img" / "representations" / f"{entity_name}.png"
    return export_animation_frame(
        skeleton_path,
        animation,
        output_path,
        frame=frame,
    )
