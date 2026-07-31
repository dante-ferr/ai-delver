"""Named level packs for CLI ``--levels @group`` expansion."""

from __future__ import annotations

import json
import re
from pathlib import Path

from src.config import config

GROUPS_FILE = config.PROJECT_ROOT / "client" / "data" / "level_groups.json"


class LevelGroupError(ValueError):
    """Invalid level-group operation."""


def load_level_groups() -> dict[str, list[str]]:
    if not GROUPS_FILE.is_file():
        return {}
    with open(GROUPS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}
    out: dict[str, list[str]] = {}
    for key, value in data.items():
        if isinstance(value, list):
            out[str(key)] = [str(item) for item in value]
    return out


def save_level_groups(groups: dict[str, list[str]]) -> None:
    GROUPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(GROUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(groups, f, indent=2)
        f.write("\n")


def normalize_group_name(name: str) -> str:
    cleaned = re.sub(r"[^\w\-]+", "_", str(name).strip())
    if not cleaned:
        raise LevelGroupError("group name must contain letters, digits, _ or -")
    return cleaned


def expand_level_list(input_levels: list[str]) -> list[str]:
    """Expand ``@group`` tokens using ``level_groups.json``; pass other names through."""
    groups = load_level_groups()
    expanded: list[str] = []
    for item in input_levels:
        token = item.strip()
        if not token:
            continue
        if token.startswith("@"):
            key = token[1:]
            if key in groups:
                expanded.extend(groups[key])
            else:
                expanded.append(token)
        else:
            expanded.append(token)
    return expanded


def add_level_group(
    name: str,
    levels: list[str] | None = None,
    *,
    replace: bool = False,
) -> list[str]:
    """Create or update a group. Returns the stored level list.

    If the group already exists and ``replace`` is False, raises ``LevelGroupError``.
    """
    key = normalize_group_name(name)
    groups = load_level_groups()
    if key in groups and not replace:
        raise LevelGroupError(
            f"group '@{key}' already exists ({len(groups[key])} levels). "
            "Pass --replace to overwrite."
        )
    cleaned = [lvl.strip() for lvl in (levels or []) if lvl and lvl.strip()]
    groups[key] = cleaned
    save_level_groups(groups)
    return cleaned


def delete_level_group(name: str) -> list[str]:
    """Remove a group from ``level_groups.json``. Returns the removed level list."""
    key = normalize_group_name(name).lstrip("@")
    groups = load_level_groups()
    if key not in groups:
        raise LevelGroupError(f"group '@{key}' not found")
    removed = groups.pop(key)
    save_level_groups(groups)
    return removed
