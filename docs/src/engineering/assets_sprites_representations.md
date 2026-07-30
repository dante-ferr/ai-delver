# Image Assets: Sprites & Representations

How world-object images are laid out under `assets/img/`.

## Two folders

| Folder | Role |
| :--- | :--- |
| `img/sprites/` | Canonical **in-game** art. Runtime (and any play client) loads from here. |
| `img/representations/` | **Editor-only overrides** when the level-editor icon must look different from the sprite. |

If the editor can show the same PNG the game uses, put the file only under `sprites/`. Do not keep a duplicate under `representations/`.

## Resolution

The level editor resolves palette / canvas images with `level.resolve_editor_object_image`:

1. `img/representations/…` if a file exists  
2. else `img/sprites/…`

Runtime goal (and other play sprites) always use `img/sprites/` — never representations.

### Path shapes

- Plain object: `{root}/{name}.png` — e.g. `sprites/platform.png`
- Variation: `{root}/{name}/{variation}.png` — e.g. `sprites/goal/oil_drink.png`

## Current examples

- **Goal variations** — only under `sprites/goal/`; editor falls back to those PNGs.
- **Platform** — `sprites/platform.png` for the editor palette (tilemap art stays in `tilesets/`).
- **Delver** — skeletal data in `sprites/delver/`; editor uses `representations/delver.png` (idle still) because it differs from the runtime skeleton.

## Regenerating DragonBones exports

After editing an entity's `*_ske.json`, `*_tex.json`, or `*_tex.png`, regenerate derived assets:

```bash
make regen-dragonbones
# headless: xvfb-run -a make regen-dragonbones
```

This exports `img/representations/{name}.png` for every DragonBones folder under `img/sprites/` (directory containing `{name}_ske.json`). Delver also regenerates its preview GIFs (`delver_idle.gif`, `delver_run.gif`).

Each entity's representation pose is configured under `[dragonbones.<name>]` in `client/src/config.toml` (`representation_animation`, `representation_frame`). New skeletal entities need their own table. Delver GIF export knobs live under `[delver_gif]`.
