"""Discover DragonBones entity folders under assets/img/sprites/."""

from __future__ import annotations

from pathlib import Path

from src.config import config


def discover_dragonbones_entities() -> list[Path]:
    """
    Return skeleton directories that contain ``{dirname}_ske.json``.

    Folder name must match the DragonBones project name prefix.
    """
    sprites_root = config.ASSETS_PATH / "img" / "sprites"
    if not sprites_root.is_dir():
        return []

    entities: list[Path] = []
    for path in sorted(sprites_root.iterdir()):
        if not path.is_dir():
            continue
        ske = path / f"{path.name}_ske.json"
        if ske.is_file():
            entities.append(path)
    return entities
