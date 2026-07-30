"""Delver-only GIF exports (idle / run UI previews)."""

from __future__ import annotations

from pathlib import Path

from src.config import config

from ._import_exporters import ensure_dragonbones_on_path


def export_delver_gifs(skeleton_path: Path) -> list[Path]:
    """Export configured Delver animation GIFs next to the skeleton assets."""
    ensure_dragonbones_on_path()
    from pyglet_dragonbones.utils.export_animation_gif import export_animation_gif

    animations = list(config.DELVER_GIF.ANIMATIONS)
    scale = float(config.DELVER_GIF.SCALE)
    antialias = bool(config.DELVER_GIF.ANTIALIAS)

    exported: list[Path] = []
    for animation_name in animations:
        output_path = skeleton_path / f"delver_{animation_name}.gif"
        export_animation_gif(
            skeleton_path,
            animation_name,
            output_path,
            scale=scale,
            antialias=antialias,
        )
        exported.append(output_path)
    return exported
