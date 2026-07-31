"""Discover handcrafted and generated level saves for the playtest browser."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from level.resolve_level import generated_levels_dir, handcrafted_levels_dir, saves_root


@dataclass(frozen=True)
class LevelEntry:
    """One playable level save."""

    name: str
    level_dir: Path
    level_json: Path
    source: str  # "handcrafted" | "generated"
    display_label: str
    # Path or bare name safe for resolve_level_dir / play-level --level
    play_ref: str


def list_playable_levels() -> list[LevelEntry]:
    """Return all ``level.json`` dirs under handcrafted/ and generated/."""
    root = saves_root()
    entries: list[LevelEntry] = []

    handcrafted = handcrafted_levels_dir()
    if handcrafted.is_dir():
        for level_json in sorted(handcrafted.rglob("level.json")):
            level_dir = level_json.parent
            rel = level_dir.relative_to(root).as_posix()
            entries.append(
                LevelEntry(
                    name=level_dir.name,
                    level_dir=level_dir,
                    level_json=level_json,
                    source="handcrafted",
                    display_label=rel,
                    play_ref=str(level_dir.resolve()),
                )
            )

    generated = generated_levels_dir()
    if generated.is_dir():
        for level_json in sorted(generated.rglob("level.json")):
            level_dir = level_json.parent
            rel = level_dir.relative_to(root).as_posix()
            entries.append(
                LevelEntry(
                    name=level_dir.name,
                    level_dir=level_dir,
                    level_json=level_json,
                    source="generated",
                    display_label=rel,
                    play_ref=str(level_dir.resolve()),
                )
            )

    return entries
