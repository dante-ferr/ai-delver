"""Orchestrate DragonBones representation (and Delver GIF) regeneration."""

from __future__ import annotations

from pathlib import Path

from ._delver_gifs import export_delver_gifs
from ._discover import discover_dragonbones_entities
from ._representation import export_entity_representation, representation_settings


def regen_all(*, verbose: bool = True) -> list[Path]:
    """
    Regenerate editor representations for every DragonBones entity.

    Delver additionally regenerates its configured preview GIFs.
    """
    entities = discover_dragonbones_entities()
    if not entities:
        if verbose:
            print("No DragonBones entities found under assets/img/sprites/.")
        return []

    written: list[Path] = []
    for skeleton_path in entities:
        name = skeleton_path.name
        animation, frame = representation_settings(name)
        if verbose:
            print(
                f"[{name}] representation ← animation={animation!r} frame={frame}"
            )
        output = export_entity_representation(skeleton_path)
        written.append(output)
        if verbose:
            print(f"[{name}] wrote {output}")

        if name == "delver":
            if verbose:
                print("[delver] exporting preview GIFs…")
            for gif_path in export_delver_gifs(skeleton_path):
                written.append(gif_path)
                if verbose:
                    print(f"[delver] wrote {gif_path}")

    return written
