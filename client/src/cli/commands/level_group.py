"""CLI: list / add / delete named level groups in level_groups.json."""

from __future__ import annotations

import json
import shutil
import sys

from level.resolve_level import generated_levels_dir
from utils.level_groups import (
    LevelGroupError,
    add_level_group,
    delete_level_group,
    load_level_groups,
    normalize_group_name,
)


def print_json(event: str, **kwargs):
    print(json.dumps({"event": event, **kwargs}), flush=True)


def run_level_group(args):
    action = getattr(args, "group_action", None)
    if action == "list":
        _list_groups()
    elif action == "add":
        _add_group(args)
    elif action == "delete":
        _delete_group(args)
    else:
        print_json("error", message="Unknown level-group action.")
        sys.exit(1)


def _list_groups() -> None:
    groups = load_level_groups()
    print_json(
        "level_groups",
        groups={name: {"count": len(levels), "levels": levels} for name, levels in groups.items()},
        message=f"{len(groups)} group(s) in level_groups.json.",
    )


def _add_group(args) -> None:
    levels_csv = getattr(args, "levels", None) or ""
    levels = [part.strip() for part in levels_csv.split(",") if part.strip()]
    replace = bool(getattr(args, "replace", False))
    try:
        stored = add_level_group(str(args.name), levels, replace=replace)
        key = normalize_group_name(str(args.name))
    except LevelGroupError as exc:
        print_json("error", message=str(exc))
        sys.exit(1)

    print_json(
        "level_group_added",
        group=key,
        levels=stored,
        count=len(stored),
        replaced=replace,
        message=f"Group '@{key}' saved with {len(stored)} level(s).",
    )


def _delete_group(args) -> None:
    delete_files = bool(getattr(args, "delete_files", False))
    try:
        key = normalize_group_name(str(args.name)).lstrip("@")
        removed = delete_level_group(key)
    except LevelGroupError as exc:
        print_json("error", message=str(exc))
        sys.exit(1)

    deleted_dir = None
    if delete_files:
        pack_dir = generated_levels_dir() / key
        if pack_dir.is_dir():
            shutil.rmtree(pack_dir)
            deleted_dir = str(pack_dir)

    print_json(
        "level_group_deleted",
        group=key,
        levels=removed,
        count=len(removed),
        deleted_files_path=deleted_dir,
        message=(
            f"Removed group '@{key}' ({len(removed)} level(s))"
            + (f" and deleted '{deleted_dir}'." if deleted_dir else ".")
        ),
    )
