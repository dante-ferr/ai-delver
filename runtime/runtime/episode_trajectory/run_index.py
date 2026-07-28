"""Lightweight per-run index stored in trajectory metadata.json.

Used by the GUI run grid so it does not need to open every trajectory JSON
just to paint level / outcome cells.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

KIND_TRAIN = "train"
KIND_PLAY = "play"
RUN_INDEX_KEY = "run_index"


def extract_run_index_entry(
    trajectory_data: dict[str, Any] | str,
    *,
    kind: str | None = None,
    cycle: int | None = None,
) -> dict[str, Any]:
    """Build one run-index row from a trajectory dict or JSON string."""
    if isinstance(trajectory_data, str):
        data = json.loads(trajectory_data)
    else:
        data = trajectory_data

    resolved_kind = kind if kind is not None else data.get("kind", KIND_TRAIN)
    if resolved_kind not in (KIND_TRAIN, KIND_PLAY):
        resolved_kind = KIND_TRAIN

    frames = data.get("frame_snapshots")
    actions = data.get("delver_actions")
    if isinstance(frames, list) and frames:
        steps = len(frames)
    elif isinstance(actions, list):
        steps = len(actions)
    else:
        steps = None

    entry: dict[str, Any] = {
        "level_hash": str(data.get("level_hash", "") or ""),
        "victorious": bool(data.get("victorious", False)),
        "kind": resolved_kind,
        "total_reward": data.get("total_reward"),
        "jump_takeoffs": data.get("jump_takeoffs"),
        "policy_confidence": data.get("policy_confidence"),
        "steps": steps,
        "actions_per_second": data.get("actions_per_second"),
        "cycle": cycle if cycle is not None else data.get("cycle"),
    }
    return entry


def entry_from_trajectory_file(
    path: Path,
    *,
    kind_fallback: str = KIND_TRAIN,
    cycle: int | None = None,
) -> dict[str, Any] | None:
    """Load light fields from a trajectory_*.json file."""
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logging.warning("Could not read trajectory for run index (%s): %s", path, exc)
        return None

    if not isinstance(data, dict):
        return None
    return extract_run_index_entry(data, kind=data.get("kind", kind_fallback), cycle=cycle)


def _pad_run_index(run_index: list, target_len: int) -> None:
    while len(run_index) < target_len:
        run_index.append(None)


def append_run_index_entry(
    metadata: dict[str, Any],
    index: int,
    entry: dict[str, Any],
) -> None:
    """Pad/append ``run_index`` so ``metadata['run_index'][index] == entry``."""
    run_index = metadata.setdefault(RUN_INDEX_KEY, [])
    if not isinstance(run_index, list):
        run_index = []
        metadata[RUN_INDEX_KEY] = run_index

    _pad_run_index(run_index, index)
    if len(run_index) == index:
        run_index.append(entry)
    else:
        run_index[index] = entry


def ensure_run_index(
    metadata: dict[str, Any],
    trajectory_dir: Path,
    *,
    write_missing: bool = True,
    only_indices: list[int] | None = None,
) -> list[dict[str, Any] | None]:
    """Ensure ``metadata['run_index']`` covers ``trajectory_count``.

    Missing or null slots are filled by reading ``trajectory_{i}.json``.
    When ``only_indices`` is set, only those slots are backfilled (lazy path).
    Returns the (possibly updated) run_index list.
    """
    count = int(metadata.get("trajectory_count", 0) or 0)
    run_index = metadata.get(RUN_INDEX_KEY)
    if not isinstance(run_index, list):
        run_index = []
        metadata[RUN_INDEX_KEY] = run_index

    kinds = metadata.get("trajectory_kinds")
    if not isinstance(kinds, list):
        kinds = []

    changed = False
    _pad_run_index(run_index, count)
    if len(run_index) > count:
        del run_index[count:]
        changed = True

    if only_indices is None:
        targets = range(count)
    else:
        targets = [i for i in only_indices if 0 <= i < count]

    for i in targets:
        existing = run_index[i] if i < len(run_index) else None
        if isinstance(existing, dict) and "victorious" in existing and "kind" in existing:
            continue

        kind_fallback = kinds[i] if i < len(kinds) else KIND_TRAIN
        path = trajectory_dir / f"trajectory_{i}.json"
        if not path.is_file():
            if not isinstance(existing, dict):
                run_index[i] = {
                    "level_hash": "",
                    "victorious": False,
                    "kind": kind_fallback if kind_fallback in (KIND_TRAIN, KIND_PLAY) else KIND_TRAIN,
                    "total_reward": None,
                    "jump_takeoffs": None,
                    "policy_confidence": None,
                    "steps": None,
                    "actions_per_second": None,
                    "cycle": None,
                }
                changed = True
            continue

        entry = entry_from_trajectory_file(path, kind_fallback=kind_fallback)
        if entry is None:
            continue
        if isinstance(existing, dict) and existing.get("cycle") is not None:
            if entry.get("cycle") is None:
                entry["cycle"] = existing["cycle"]
        run_index[i] = entry
        changed = True

    if changed and write_missing:
        metadata[RUN_INDEX_KEY] = run_index

    return run_index


def read_run_index_sync(
    trajectory_dir: Path,
    *,
    backfill_all: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any] | None]]:
    """Sync read metadata and optionally backfill the full run_index.

    Default is cheap: pad the list to ``trajectory_count`` without opening
    trajectory files. Callers can lazily fill visible slots via
    ``ensure_run_index(..., only_indices=...)``.
    """
    meta_path = trajectory_dir / "metadata.json"
    if not meta_path.is_file():
        empty: dict[str, Any] = {"trajectory_count": 0, "stats": {"amount": 0, "victories": 0}}
        return empty, []

    try:
        with open(meta_path, "r") as f:
            metadata = json.load(f)
    except (OSError, json.JSONDecodeError):
        empty = {"trajectory_count": 0, "stats": {"amount": 0, "victories": 0}}
        return empty, []

    if not isinstance(metadata, dict):
        empty = {"trajectory_count": 0, "stats": {"amount": 0, "victories": 0}}
        return empty, []

    count = int(metadata.get("trajectory_count", 0) or 0)
    run_index = metadata.get(RUN_INDEX_KEY)
    if not isinstance(run_index, list):
        run_index = []
        metadata[RUN_INDEX_KEY] = run_index

    before_len = len(run_index)
    _pad_run_index(run_index, count)
    if len(run_index) > count:
        del run_index[count:]

    if backfill_all:
        before = json.dumps(run_index, sort_keys=True, default=str)
        run_index = ensure_run_index(metadata, trajectory_dir, write_missing=True)
        after = json.dumps(run_index, sort_keys=True, default=str)
        if before != after or before_len != len(run_index):
            try:
                with open(meta_path, "w") as f:
                    json.dump(metadata, f, indent=4)
            except OSError as exc:
                logging.warning("Failed to persist run_index backfill: %s", exc)
    elif before_len != len(run_index):
        metadata[RUN_INDEX_KEY] = run_index
        try:
            with open(meta_path, "w") as f:
                json.dump(metadata, f, indent=4)
        except OSError as exc:
            logging.warning("Failed to persist run_index pad: %s", exc)

    return metadata, run_index
