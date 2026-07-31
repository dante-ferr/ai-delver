"""Resolve level names/paths across handcrafted, generated, and legacy saves."""

from __future__ import annotations

from pathlib import Path

from level.config import config as level_config
from level.exceptions import LevelError


class LevelResolveError(LevelError):
    """Raised when a level name or path cannot be resolved to level.json."""


def saves_root() -> Path:
    """Absolute ``client/data/level_saves`` (CWD=client or repo root)."""
    relative = Path(level_config.LEVEL_SAVE_FOLDER_PATH)
    if relative.is_absolute():
        return relative

    cwd_candidate = (Path.cwd() / relative).resolve()
    if cwd_candidate.is_dir():
        return cwd_candidate

    repo_candidate = (level_config.PROJECT_ROOT / "client" / relative).resolve()
    if repo_candidate.is_dir():
        return repo_candidate

    # Prefer client CWD convention even if the folder was just created.
    if (Path.cwd() / "data").is_dir() or (Path.cwd() / "src").is_dir():
        return cwd_candidate
    return repo_candidate


def handcrafted_levels_dir() -> Path:
    return saves_root() / "handcrafted"


def generated_levels_dir() -> Path:
    return saves_root() / "generated"


def resolve_level_json(name_or_path: str | Path) -> Path:
    """Resolve a level name or path to an existing ``level.json`` file.

    Candidate order:
    1. Direct path / ``…/level.json``
    2. ``handcrafted/<name>/level.json``
    3. ``generated/<name>/level.json`` and ``generated/*/<name>/level.json``
    4. Legacy flat ``level_saves/<name>/level.json``
    """
    text = str(name_or_path).strip()
    if not text:
        raise LevelResolveError("level name or path must not be empty")

    raw = Path(text)
    saves = saves_root()
    handcrafted = saves / "handcrafted"
    generated = saves / "generated"

    candidates: list[Path] = [
        raw,
        raw / "level.json",
        Path.cwd() / raw,
        Path.cwd() / raw / "level.json",
        level_config.PROJECT_ROOT / raw,
        level_config.PROJECT_ROOT / raw / "level.json",
    ]

    # Bare name (no path separators): search save roots by name.
    normalized = text.replace("\\", "/").rstrip("/")
    if "/" not in normalized and not normalized.endswith(".json"):
        name = normalized
        candidates.extend(
            [
                handcrafted / name / "level.json",
                generated / name / "level.json",
                saves / name / "level.json",
            ]
        )
        if generated.is_dir():
            for pack_dir in sorted(p for p in generated.iterdir() if p.is_dir()):
                candidates.append(pack_dir / name / "level.json")
    else:
        rel = Path(normalized)
        if rel.suffix == ".json":
            candidates.extend([handcrafted / rel, generated / rel, saves / rel])
        else:
            candidates.extend(
                [
                    handcrafted / rel / "level.json",
                    generated / rel / "level.json",
                    saves / rel / "level.json",
                ]
            )

    seen: set[Path] = set()
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_file():
            return resolved

    raise LevelResolveError(f"could not resolve level '{name_or_path}'")


def resolve_level_dir(name_or_path: str | Path) -> Path:
    """Resolve to the directory containing ``level.json``."""
    return resolve_level_json(name_or_path).parent
