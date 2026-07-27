from pathlib import Path


def resolve_editor_object_image(
    assets_path: Path,
    object_name: str,
    variation: str | None = None,
) -> Path:
    """Resolve a level-editor image for a world object.

    Lookup order:

    1. ``img/representations/…`` — editor-only override when the canvas icon
       must differ from in-game art (e.g. Delver idle still vs DragonBones).
    2. ``img/sprites/…`` — canonical game art; use this when the editor can
       show the same PNG the runtime uses.

    Paths:

    - no variation: ``{root}/{object_name}.png``
    - with variation: ``{root}/{object_name}/{variation}.png``
    """
    relative = (
        Path(object_name) / f"{variation}.png"
        if variation is not None
        else Path(f"{object_name}.png")
    )
    candidates = [
        assets_path / "img" / "representations" / relative,
        assets_path / "img" / "sprites" / relative,
    ]
    for path in candidates:
        if path.is_file():
            return path

    searched = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(
        f"No editor image for '{object_name}'"
        + (f" variation '{variation}'" if variation is not None else "")
        + f". Looked in: {searched}"
    )
